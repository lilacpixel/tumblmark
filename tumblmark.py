#!/usr/bin/env python

from bs4 import BeautifulSoup, Comment
from datetime import datetime
from markdownify import MarkdownConverter
from rich import print
from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.prompt import Confirm
from rich.prompt import Prompt
from rich.progress import track

import argparse
import configparser
import os
import pytumblr
import re
import sys
import time
import urllib.request

# define functions for custom Markdown converter
class FixMarkup(MarkdownConverter):
	def convert_div(self, el, text, parent_tags):
		# wrapper for ask and reblog posts
		if 'class' in el.attrs and el.attrs['class'][0] in ('question', 'reblog'):
			lines = text.splitlines()
			counter = 0
			while counter < len(lines):
				lines[counter] = '    ' + lines[counter]
				counter += 1
			if 'question' in el.attrs['class']:
				if 'data-user-url' in el.attrs:
					user = '[' + el.attrs['data-username'] + '](' + el.attrs['data-user-url'] + ')'
				elif 'data-username' in el.attrs:
					user = el.attrs['data-username']
				else:
					user = 'Anonymous'
				question = '    **' + user + ':**\n\n' + '\n'.join(lines)
				return '!!! note ""\n' + question + '\n'
			else:
				if 'data-timestamp' in el.attrs:
					title = el.attrs['data-timestamp']
				else:
					title = 'Reblog'
				return '!!! quote "' + title + '"\n' + '\n'.join(lines) + '\n'
		else:
			return super().convert_div(el, text, parent_tags)
	def convert_figure(self, el, text, parent_tags):
		# pass through figure tags as-is
		if 'class' in el.attrs and 'audio' in el.attrs['class']:
			return str(el)
		else:
			return super().convert_figure(el, text, parent_tags)
	def convert_iframe(self, el, text, parent_tags):
		# pass through iframe tags as-is
		return str(el)
	def convert_p(self, el, text, parent_tags):
		# pass through headings and Tumblr formatting
		if (
			('class' in el.attrs and el.attrs['class'][0] in ('h1', 'h2')) or
			('class' in el.attrs and el.attrs['class'][0] in ('chat-text', 'cursive-text', 'quote-text'))
		):
			return str(el) + '\n'
		# pass through image row tags
		if 'class' in el.attrs and 'image-row' in el.attrs['class']:
			return '<p class="image-row" markdown="span">' + text + '</p>'
		else:
			return super().convert_p(el, text, parent_tags)
	# pass through other formatting tags
	def convert_small(self, el, text, parent_tags):
		return str(el)
	def convert_span(self, el, text, parent_tags):
		return str(el)
	# pass through video tags
	def convert_video(self, el, text, parent_tags):
		return str(el)

def md(html, **options):
	return FixMarkup(**options).convert(html)

# additional processing of output HTML with Beautiful Soup
def bs_process(soup, username):
	# preserve comment tags that are used to create read more links
	for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
		if comment.strip() == 'more':
			comment.replace_with('<!-- more -->')
	# adjust output of Tumblr-specified iframes
	for iframe in soup.find_all('iframe'):
		# use small height for Spotify players
		if 'class' in iframe and 'spotify_audio_player' in iframe['class']:
			iframe.attrs['height'] = '152'
		# adjust default dimensions of YouTube embeds and use nocookie URLs
		if 'youtube.com' in iframe.attrs['src']:
			iframe.attrs['src'] = iframe.attrs['src'].replace('youtube.com', 'youtube-nocookie.com').split('?')[0]
			iframe.attrs['width'] = '500'
			iframe.attrs['height'] = '280'
	return soup

# check requested posts before saving to disk
def check_posts(client, username, total_posts, offset, path, args, saved_posts):
	# if the number of remaining posts is less than the API's batch size of 20, only request what's there
	if total_posts < 20:
		batch = total_posts
	elif total_posts - offset < 20:
		batch = total_posts - offset
	else:
		batch = 20
	response = client.posts(username + '.tumblr.com', npf=True, offset=offset, reblog_info=True)
	for i, post in enumerate(response['posts'], start=1):
		state = post['state']
		if 'parent_post_url' in post:
			# if there is a parent post, make sure it belongs to the user
			split = re.split(r'https?:\/\/|\/[^\/]*$', post['parent_post_url'])
			if username in split[1]:
				# self-reblog
				if state == 'published' or (state == 'draft' and args.draft == True) or (state == 'private' and args.private == True):
					saved_posts += 1
					save_post(client, post, 'reblog', username, path)
		else:
			# original post
			if state == 'published' or (state == 'draft' and args.draft == True) or (state == 'private' and args.private == True):
				saved_posts += 1
				save_post(client, post, 'original', username, path)

		# increment offset
		offset += 1
		
		if i == batch:
			posts = {'offset': offset, 'saved_posts': saved_posts}
			return posts

# download embedded audio, images, and video
def download_media(url, type, path):
	media_path = path + type + '/'
	if not os.path.exists(media_path):
		os.makedirs(media_path)
	filename = url.split('/')[-1].split('?')[0]
	urllib.request.urlretrieve(url, media_path + filename)
	return type + '/' + filename

# get ask content for ask posts
def get_ask(ask, post, blocks, path):
	ask_content = []
	ask_content.insert(0, '<div class="question"' + ask['name'] + ask['url'] + '>')
	for i, block in enumerate(blocks[0:ask['end'] + 1]):
		ask_content.append(get_block(post['content'][i], post, i, path))
	ask_content.insert(ask['end'] + 2, '</div>')
	return ''.join(ask_content)

# get length and attribution info for ask posts
def get_ask_info(layout):
	ask = dict()
	ask['name'] = ''
	ask['url'] = ''
	ask['end'] = layout['blocks'][-1]
	if 'attribution' in layout:
		if 'blog' in layout['attribution']:
			ask['name'] = ' data-username="' + layout['attribution']['blog']['name'] + '"'
			ask['url'] = ' data-user-url="' + layout['attribution']['blog']['url'] + '"'
	return ask

# get block from post content
def get_block(block, post, index, path):
	content = post['content']
	type = block['type']
	if type == 'audio':
		if block['provider'] == 'tumblr':
			track_info_list = []
			album = ''
			cover = ''
			if block['title']:
				track_info_list.append(block['title'])
			if block['artist']:
				track_info_list.insert(0, block['artist'])
			track_info = ' - '.join(track_info_list)
			if block['album']:
				album = '<div class="audio__album">' + block['album'] + '</div>'
			if block['poster']:
				cover = '<img src="/' + download_media(block['poster'][0]['url'], 'img', path) + '" alt="' + track_info + '">'
			return '<figure class="audio">' + cover + '<div class="audio__wrapper"><figcaption class="audio__title">' + track_info + '</figcaption>' + album + '<audio src="/' + download_media(block['media']['url'], 'audio', path) + '" controls></audio></div></figure>'
		else:
			if 'embed_html' in block:
				if block['embed_html'] != '':
					return block['embed_html']
				else:
					track_info_list = []
					if block in ('artist', 'title'):
						if block['title']:
							track_info_list.append(block['title'])
						if block['artist']:
							track_info_list.insert(0, block['artist'])
					else:
						track_info_list.append('Audio Link')
					track_info = ' - '.join(track_info_list)
					return '<a href="' + block['url'] + '">' + track_info + '</a>'
	if type == 'image':
		if 'alt_text' in block:
			alt = block['alt_text'].replace('"', '&quot;')
		else:
			alt = ''
		# download and return largest available image file
		return '<img src="' + download_media(block['media'][0]['url'], 'img', path) + '" alt="' + alt + '">'
	if type == 'link':
		return '<p><a href="' + block['url'] + '">' + block['title'] + '</a></p>'
	if type == 'text':
		text_list = list(block['text'])
		if 'formatting' in block:
			# create list for all formatting in block
			format_list = []
			# set start and end tags to be inserted for formatting
			for formatting in block['formatting']:
				type = formatting['type']
				if type == 'bold':
					start_tag = '<strong>'
					end_tag = '</strong>'
				elif type == 'color':
					start_tag = '<span style="color: ' + formatting['hex'] + ';">'
					end_tag = '</span>'
				elif type == 'italic':
					start_tag = '<em>'
					end_tag = '</em>'
				elif type == 'link':
					start_tag = '<a href="' + formatting['url'] + '">'
					end_tag = '</a>'
				elif type == 'mention':
					start_tag = '<a href="' + formatting['blog']['url'] + '">'
					end_tag = '</a>'
				elif type == 'small':
					start_tag = '<small>'
					end_tag = '</small>'
				elif type == 'strikethrough':
					start_tag = '<del>'
					end_tag = '</del>'
				else:
					print('[b red]Error:[/] No formatting for type ' + type)
				# append tags and start and end positions to list
				format_list.append({'position': formatting['start'], 'tag': start_tag})
				format_list.append({'position': formatting['end'], 'tag': end_tag})
			# sort list so that all formatting will be applied sequentially
			format_list = sorted(format_list, key=lambda x: x['position'])
			# insert tags at specified locations
			for i, format in enumerate(format_list):
				text_list.insert(format['position'] + i, format['tag'])
		# join list into string
		text = ''.join(text_list)
		if 'subtype' in block:
			subtype = block['subtype']
			if subtype == 'chat':
				text = '<p class="chat-text">' + text + '</p>'
			elif subtype == 'heading1':
				if 'post' in post or index > 0:
					text = '<p class="h1">' + text + '</p>'
				else:
					text = '<h1>' + text + '</h1>'
			elif subtype == 'heading2':
				text = '<p class="h2">' + text + '</p>'
			elif subtype == 'indented':
				text = '<blockquote><p>' + text + '</p></blockquote>'
			elif subtype.endswith('list-item'):
				text = ''.join(text_list)
				text_list = []
				# set values for current, previous, and next items
				current_item_subtype = block['subtype']
				if 'indent_level' in block:
					current_indent_level = block['indent_level']
				else:
					current_indent_level = 0
				# set default values for previous and next items
				previous_item_subtype = None
				previous_indent_level = 0
				next_item_subtype = None
				next_indent_level = 0
				# if previous and next items exist in the range, assign actual values
				if 0 <= index - 1 < len(content):
					if 'subtype' in content[index - 1]:
						previous_item_subtype = content[index - 1]['subtype']
					if 'indent_level' in content[index - 1]:
						previous_indent_level = content[index - 1]['indent_level']
				if 0 <= index + 1 < len(content):
					if 'subtype' in content[index + 1]:
						next_item_subtype = content[index + 1]['subtype']
					if 'indent_level' in content[index + 1]:
						next_indent_level = content[index + 1]['indent_level']
				# set start and end tags for current item subtype
				if current_item_subtype.startswith('unordered'):
					start_tag = '<ul>'
					end_tag = '</ul>'
				else:
					start_tag = '<ol>'
					end_tag = '</ol>'
				# if previous tag does not exist, is of a different subtype, or has a lower indent level, output start tag
				if (
					previous_item_subtype == None or
					previous_item_subtype != current_item_subtype or
					previous_indent_level < current_indent_level
				):
					text_list.append(start_tag)
				text_list.append('<li>' + text)
				# close list item if next indent level will be the same or less or if the item type changes
				if next_indent_level <= current_indent_level or next_item_subtype != current_item_subtype:
					text_list.append('</li>')
				# if next tag does not exist, is of a different subtype, or has a lower indent level, output end tag(s)
				if (
					next_item_subtype == None or
					next_item_subtype != current_item_subtype or
					next_indent_level < current_indent_level
				):
					# output end tags equal to the number of nested levels we need to close
					# if indent levels are the same, subtype is different
					if next_indent_level == current_indent_level:
						counter = 1
					else:
						counter = current_indent_level - next_indent_level
					while counter > 0:
						text_list.append(end_tag)
						# close list item if there is no following list item or if the indent level is decreasing
						if not (
							next_item_subtype == None or
							next_indent_level > current_indent_level
						):
							text_list.append('</li>')
						counter -= 1
				text = '\n'.join(text_list)
			elif subtype == 'quirky':
				text = '<p class="cursive-text">' + text + '</p>'
			elif subtype == 'quote':
				text = '<p class="quote-text">' + text + '</p>'
			else:
				print('[b red]Error:[/] No formatting for subtype ' + subtype)
		else:
			text = '<p>' + text + '</p>'
		return text
	if type == 'video':
		if 'embed_html' in block:
			if block['embed_html'] != '':
				return block['embed_html']
			else:
				return '<a href="' + block['url'] + '">Video Link</a>'
		else:
			return '<video width="' + str(block['media']['width']) + '" height="' + str(block['media']['height']) + '" controls><source src="/' + download_media(block['media']['url'], 'video', path) + '" type="' + block['media']['type'] + '">This device does not support native HTML5 video.</video>'

# get layout for ask posts and posts with row content
def get_layout(layout, post, ask, content, path):
	layout_content = []
	reblog = False
	# if reference to original post exists, post is reblog
	if 'post' in post:
		reblog = True
		post_id = post['post']['id']
	# if truncate_after exists, set output to terminate at read more link
	if reblog == True and 'truncate_after' in layout:
		block_end = layout['truncate_after'] + 1
	else:
		block_end = len(content)
	# for asks, set layout start to end of ask block and pass ask to get_ask
	if ask != None:
		block_start = ask['end'] + 1
		layout_content.append(get_ask(ask, post, layout['display'], path))
	else:
		block_start = 0
	for row_index, row in enumerate(layout['display'][block_start:block_end]):
		# check first block in row
		first_block = content[row['blocks'][0]]['type']
		# if first block is an image and there are multiple in the row, wrap them in an image row
		if first_block == 'image' and len(row['blocks']) > 1:
			images = []
			images.append('<p class="image-row" markdown="span">')
			for i, block_index in enumerate(row['blocks']):
				images.append(get_block(content[block_index], post, i, path))
			images.append('</p>')
			layout_content.insert(row['blocks'][0], ''.join(images))
		else:
			for i, block_index in enumerate(row['blocks']):
				layout_content.append(get_block(content[block_index], post, i, path))
		if 'truncate_after' in layout:
			# output read more link for non-reblog post
			if reblog == False and row_index == layout['truncate_after']:
				layout_content.append('<!-- more -->')
	# read more links on reblog posts should redirect to original
	if block_end < len(content):
		layout_content.append('<a href="/post/' + post_id + '">View original post</a>')
	return layout_content

# get original post dates for posts in reblog chain
def get_post_date(client, username, id):
	try:
		response = client.posts(username + '.tumblr.com', npf=True, id=id)
		original_reblog = response['posts'][0]
	except Exception as e:
		print('[b red]Error:[/] ' + str(e))
		post_date = ''
	else:
		post_date = ' data-timestamp="' + datetime.fromtimestamp(original_reblog['timestamp']).strftime('%B %-d, %Y') + '"'
	return post_date

# save post and content to disk
def save_post(client, post, type, username, path):
	# initialize variables
	ask = None
	body_list = []
	content = post['content']

	# post contains ask or row-based layouts
	if post['layout']:
		for layout in post['layout']:
			if layout['type'] == 'ask':
				ask = get_ask_info(layout)
				# if post is a legacy ask, pass content to get_block directly
				if len(post['layout']) == 1:
					body_list.append(get_ask(ask, post, layout['blocks'], path))
					for i, block in enumerate(content[ask['end'] + 1:]):
						body_list.append(get_block(block, post, i, path))
			# for other layout-based posts, use get_layout
			else:
				layout_content = get_layout(layout, post, ask, content, path)
				body_list.append(''.join(layout_content))
	else:
		for i, block in enumerate(content):
			body_list.append(get_block(block, post, i, path))

	# post contains reblogs
	if post['trail']:
		reblogs = []
		for reblog in post['trail']:
			# use get_layout for reblogs with layout content
			if reblog['layout']:
				for layout in reblog['layout']:
					post_date = get_post_date(client, username, reblog['post']['id'])
					reblog_content = get_layout(layout, reblog, ask, reblog['content'], path)
					reblogs.append('<div class="reblog"' + post_date + '>' + ''.join(reblog_content) + '</div>')
			# for all others, use get_block
			else:
				post_date = get_post_date(client, username, reblog['post']['id'])
				reblog_content = []
				for i, content in enumerate(reblog['content']):
					reblog_content.append(get_block(content, reblog, i, path))
				reblogs.append('<div class="reblog"' + post_date + '>' + ''.join(reblog_content) + '</div>')
		body_list.insert(0, '\n\n'.join(reblogs))
	body = '\n'.join(body_list)

	# modify tree before Markdown conversion
	soup = BeautifulSoup(body, 'html.parser')
	soup = bs_process(soup, username)

	# populate front matter
	timestamp = post['timestamp']
	date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%S')
	# use custom titles for legacy post types
	if post['original_type'] == 'audio':
		if soup.select('figcaption.audio__title'):
			title = soup.select('figcaption.audio__title')[0].string.replace("'", "''")
		else:
			title = 'Audio'
		title = "'🎵 " + title + "'"
	elif post['original_type'] == 'chat':
		title = "'💬 Chat'"
	elif post['original_type'] == 'link':
		title = "'🔗 " + soup.a.string.replace("'", "''") + "'"
	elif post['original_type'] == 'note':
		title = "'❓ Ask'"
	elif post['original_type'] == 'video':
		title = "'🎥 Video'"
	else:
		# if the first element in the post is an H1 heading, use it as the post's title
		first_element = soup.select(':first-child')[0]
		if first_element.name == 'h1':
			title = "'" + first_element.string.replace("'", "''") + "'"
		else:
			title = "'Untitled'"
	filename = post['id_string'] + '.md'

	# append front matter
	front_matter = []
	front_matter.append('---\n')
	front_matter.append('date: ' + date + '\n')
	front_matter.append('title: ' + title + '\n')
	if post['state'] in ('draft', 'private'):
		front_matter.append("draft: true\n")
	if 'tags' in post and len(post['tags']) > 0:
		front_matter.append('tags:\n')
		for tag in post['tags']:
			front_matter.append('  - ' + tag + '\n')
	# pin metadata is only used by paid Material for MkDocs, but store the value anyway
	if 'is_pinned' in post:
		front_matter.append('pin: true\n')
	front_matter.append('---\n\n')

	# write to selected filename
	file = open(path + filename, 'w')
	file.writelines(front_matter)
	markdown_body = md(str(soup), heading_style='ATX')
	file.write(markdown_body)
	file.close()

# main function
def main():
	try:
		console = Console()

		parser = argparse.ArgumentParser(description='Exports original Tumblr posts in Markdown for MkDocs.')
		parser.add_argument("-d", "--draft", help="include draft posts in export", action="store_true")
		parser.add_argument("-p", "--private", help="include private posts in export", action="store_true")
		args = parser.parse_args()

		path = 'docs/posts/'

		print("""[royal_blue1]
▗▄▄▄▖          ▗▖   ▗▄▖  ▗▄ ▄▖          ▗▖
▝▀█▀▘          ▐▌   ▝▜▌  ▐█ █▌          ▐▌
  █  ▐▌ ▐▌▐█▙█▖▐▙█▙  ▐▌  ▐███▌ ▟██▖ █▟█▌▐▌▟▛
  █  ▐▌ ▐▌▐▌█▐▌▐▛ ▜▌ ▐▌  ▐▌█▐▌ ▘▄▟▌ █▘  ▐▙█
  █  ▐▌ ▐▌▐▌█▐▌▐▌ ▐▌ ▐▌  ▐▌▀▐▌▗█▀▜▌ █   ▐▛█▖
  █  ▐▙▄█▌▐▌█▐▌▐█▄█▘ ▐▙▄ ▐▌ ▐▌▐▙▄█▌ █   ▐▌▝▙
  ▀   ▀▀▝▘▝▘▀▝▘▝▘▀▘   ▀▀ ▝▘ ▝▘ ▀▀▝▘ ▀   ▝▘ ▀▘[/royal_blue1]

:sparkles: [b]Welcome to TumblMark.[/] :sparkles:\n""")

		# check for credentials file
		if 'credentials.txt' in os.listdir('./'):
			config = configparser.ConfigParser()
			config.read('./credentials.txt')
			credentials_list = []
			for key, value in config.items('credentials'):
				credentials_list.append('[b]' + key + ':[/] ' + ('**************************************************' if key.endswith('secret') else value))
			credentials = '\n'.join(credentials_list)
			if 'consumer_key' in config['credentials']:
				consumer_key = config.get('credentials', 'consumer_key')
			if 'secret' in config['credentials']:
				secret = config.get('credentials', 'secret')
			if 'token' in config['credentials']:
				token = config.get('credentials', 'token')
			if 'token_secret' in config['credentials']:
				token_secret = config.get('credentials', 'token_secret')

		print(Panel.fit(Padding("""To use this tool, you'll need credentials for the Tumblr API.
If you don't already have them, you can register an application here:

[b]https://www.tumblr.com/oauth/apps[/b]

For more on how to register an application, check out our documentation:

[b]https://github.com/lilacpixel/tumblmark[/]

Once you've registered an application, log in with your consumer key and
secret via the API console, then click [i]Show keys[/] at the top of the page
to view your token and token secret.

[b]https://api.tumblr.com/console[/]""", 1), border_style='royal_blue1', highlight=True))

		print()

		if 'credentials' in locals():
			print(Panel.fit(Padding(':magnifying_glass_tilted_left: [b]Found credentials file with the following values:[/]\n\n' + credentials, 1)))
			print()
			use_credentials = Confirm.ask('[b]Use these values?[/]')

		if use_credentials == False or 'consumer_key' not in locals():
			while True:
				consumer_key = Prompt.ask('[b]Enter your consumer key[/]').strip()
				if consumer_key != '':
					break
		if use_credentials == False or 'secret' not in locals():
			while True:
				secret = Prompt.ask('[b]Enter your consumer secret[/]', password=True).strip()
				if secret != '':
					break
		if use_credentials == False or 'token' not in locals():
			while True:
				token = Prompt.ask('[b]Enter your token[/]').strip()
				if token != '':
					break
		if use_credentials == False or 'token_secret' not in locals():
			while True:
				token_secret = Prompt.ask('[b]Enter your token secret[/]', password=True).strip()
				if token_secret != '':
					break

		print('\nAlmost done!\n')
		while True:
			username = Prompt.ask('Enter the [b]username[/] of the account you\'d like to export from').strip()
			if username != '':
				break

		print()

		client = pytumblr.TumblrRestClient(consumer_key, secret, token, token_secret)
		try:
			with console.status('Requesting blog info from Tumblr…'):
				response = client.blog_info(username + '.tumblr.com')
		except Exception as e:
			print('[b red]Error:[/] ' + str(e))
		else:
			if 'meta' in response and response['meta']['status'] != 200:
				errors = []
				for error in response['errors']:
					errors.append(error)
				if len(errors) > 1:
					print('[b red]Error:[/]')
					for errors in errors:
						print('- ' + error['detail'] + ' (' + error['title'] + ', code ' + str(error['code']) + ')')
				else:
					print('[b red]Error:[/] ' + error['detail'] + ' (' + error['title'] + ', code ' + str(error['code']) + ')')
			else:
				print(':tada: [b]Authenticated successfully![/]\n')

				offset = 0
				saved_posts = 0
				total_posts = response['blog']['total_posts']

				for i in track(range(offset, total_posts, 20), description='[b]Retrieving posts…[/]'):
					posts = check_posts(client, username, total_posts, offset, path, args, saved_posts)
					offset = posts['offset']
					saved_posts = posts['saved_posts']

				print('\n:white_check_mark: Checked ' + str(total_posts) + ' posts and saved ' + str(posts['saved_posts']) + ' posts in total.\n')

				print(Panel.fit(Padding("""[yellow]•[/] Edit [i]mkdocs.yml[/] to add your site name and adjust any other settings you'd like (colors, avatar, etc).
[yellow]•[/] Run [reverse]mkdocs serve[/] and navigate to [b]http://localhost:8000[/] in the browser to preview your site.
[yellow]•[/] Create any new posts and/or pages you'd like in the Markdown editor of your choice.
[yellow]•[/] Once everything is looking and working as intended, run [reverse]mkdocs build[/] to build your site!""", 1), border_style='royal_blue1', highlight=True, title=':glowing_star: [b default]Next Steps[/]', title_align='left'))

				print('\n[b]Thank you for trying TumblMark![/] :heart-emoji:\n\n:question_mark: Questions or suggestions? Let me know over on GitHub: [b]https://github.com/lilacpixel/tumblmark/issues[/]\n\nHave a great day! :cat2:\n')
	except KeyboardInterrupt:
		# exit cleanly if interrupt is received
		print('\n\nKeyboard interrupt detected; exiting! :wave:')
		sys.exit(0)

if __name__ == '__main__':
	main()