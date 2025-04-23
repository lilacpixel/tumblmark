#!/usr/bin/env python

from datetime import datetime
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
	if ask['name'] != '' and ask['url'] != '':
		asker = '**[' + ask['name'] + '](' + ask['url'] + '):**'
	else:
		asker = '**Anonymous:**'
	ask_content.insert(0, '!!! note ""\n' + '    ' + asker + '\n\n')
	for i, block in enumerate(blocks[0:ask['end'] + 1]):
		ask_content.append('    ' + get_block(post['content'][i], post, i, path))
	return ''.join(ask_content)

# get length and attribution info for ask posts
def get_ask_info(layout):
	ask = dict()
	ask['name'] = ''
	ask['url'] = ''
	ask['end'] = layout['blocks'][-1]
	if 'attribution' in layout:
		if 'blog' in layout['attribution']:
			ask['name'] = layout['attribution']['blog']['name']
			ask['url'] = layout['attribution']['blog']['url']
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
					embed = block['embed_html']
					if 'spotify_audio_player' in embed:
						embed = re.sub(r'(width=")[0-9]*(")', r'\g<1>100%\g<2>', embed)
						embed = re.sub(r'(height=")[^"]*(")', r'\g<1>152\g<2>', embed)
					return embed
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
		if 'attribution' in block:
			attribution = ' "Source: ' + block['attribution']['url'] + '"'
		else:
			attribution = ''
		if 'alt_text' in block:
			alt = block['alt_text'].replace('"', '&quot;')
		else:
			alt = ''
		# download and return largest available image file
		return '![' + alt + '](' + download_media(block['media'][0]['url'], 'img', path) + attribution + ')'
	if type == 'link':
		return '[' + block['title'] + '](' + block['url'] + ')'
	if type == 'poll':
		question = block['question']
		answers = []
		for answer in block['answers']:
			answers.append('    - [x] **' + answer['answer_text'] + '**')
		return '!!! note ""\n    <p class="h1">❓ ' + question + '</p>\n\n' + '\n'.join(answers) + '\n\n    [View original poll on Tumblr](' + post['post_url'] + '){.md-button .md-button--primary}'
	if type == 'text':
		text_list = list(block['text'])
		if 'formatting' in block:
			# set start and end tags to be inserted for formatting
			for formatting in block['formatting']:
				type = formatting['type']
				if type == 'bold':
					start_tag = '**'
					end_tag = '**'
				elif type == 'color':
					start_tag = '<span style="color: ' + formatting['hex'] + ';" markdown="span">'
					end_tag = '</span>'
				elif type == 'italic':
					start_tag = '*'
					end_tag = '*'
				elif type == 'link':
					start_tag = '['
					end_tag = '](' + formatting['url'] + ')'
				elif type == 'mention':
					start_tag = '['
					end_tag = '](' + formatting['blog']['url'] + ')'
				elif type == 'small':
					start_tag = '<small markdown="span">'
					end_tag = '</small>'
				elif type == 'strikethrough':
					start_tag = '~~'
					end_tag = '~~'
				else:
					print('[b red]Error:[/] No formatting for type ' + type)
				format_start = formatting['start']
				format_end = formatting['end']
				text_list[format_start] = start_tag + text_list[format_start]
				text_list[format_end - 1] += end_tag
		# join list into string
		text = ''.join(text_list)
		if 'subtype' in block:
			subtype = block['subtype']
			if subtype == 'chat':
				text = '<p class="chat-text" markdown="span">' + text + '</p>'
			elif subtype == 'heading1':
				if 'post' not in post and block == post['content'][0]:
					text = '# ' + text
				else:
					text = '<p class="h1" markdown="span">' + text + '</p>'
			elif subtype == 'heading2':
				text = '<p class="h2" markdown="span">' + text + '</p>'
			elif subtype == 'indented':
				text = '> ' + text
			elif subtype.endswith('list-item'):
				if 'indent_level' in block:
					indent_level = block['indent_level']
				else:
					indent_level = 0
				if block['subtype'].startswith('unordered'):
					list_item_prefix = '- '
				else:
					prefix_number = 1
					# check if previous item exists
					if 0 <= index - 1 < len(content):
						# check all previous blocks in reverse order
						for item in reversed(content[:index]):
							if 'subtype' in item:
								# check if previous item is of same subtype
								if item['subtype'] == block['subtype']:
									if 'indent_level' in item:
										item_indent_level = item['indent_level']
									else:
										item_indent_level = 0
									# check if previous item has same indent level
									# if so, increment leading numeral
									if item_indent_level == indent_level:
										prefix_number += 1
							else:
								break
					list_item_prefix = str(prefix_number) + '. '
				text = ('    ' * indent_level) + list_item_prefix + text
			elif subtype == 'quirky':
				text = '<p class="cursive-text" markdown="span">' + text + '</p>'
			elif subtype == 'quote':
				text = '<p class="quote-text" markdown="span">' + text + '</p>'
			else:
				print('[b red]Error:[/] No formatting for subtype ' + subtype)
		return text
	if type == 'video':
		if 'embed_html' in block:
			if block['embed_html'] != '':
				embed = block['embed_html']
				if 'youtube_iframe' in embed:
					embed = re.sub(r'(src="[a-z:\/\.]*)youtube\.com', r'\1youtube-nocookie.com', embed)
					embed = re.sub(r'(src="[^\?]*)\?[^"]*(")', r'\1\2', embed)
					embed = embed.replace('id=', 'class=')
					embed = re.sub(r'(width=")[0-9]*(")', r'\g<1>100%\g<2>', embed)
					embed = re.sub(r' height="[0-9]*"', '', embed)
					embed = embed.replace('  ', ' ')
				return embed
			else:
				return '[Video Link](' + block['url'] + ')'
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
		layout_content.append('[View original post](/post/' + post_id + ')')
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
		post_date = datetime.fromtimestamp(original_reblog['timestamp']).strftime('%B %-d, %Y')
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
				body_list.append('\n\n'.join(layout_content))
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
					reblogs.append('!!! quote "' + post_date + '"\n    ' + '\n\n    '.join(reblog_content))
			# for all others, use get_block
			else:
				post_date = get_post_date(client, username, reblog['post']['id'])
				reblog_content = []
				for i, content in enumerate(reblog['content']):
					reblog_content.append(get_block(content, reblog, i, path))
				reblogs.append('!!! quote "' + post_date + '"\n    ' + '\n\n    '.join(reblog_content))
		body_list.insert(0, '\n\n'.join(reblogs))
	
	# post contains source
	if 'source_url' in post:
		if 'source_title' in post:
			source_title = post['source_title']
		else:
			source_title = post['source_url']
		body_list.append('**Source:** [' + source_title + '](' + post['source_url'] + ')\n{.source}')

	body = '\n\n'.join(body_list)

	# populate front matter
	timestamp = post['timestamp']
	date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%S')
	# use custom titles for legacy post types
	if post['original_type'] == 'audio':
		if 'figcaption' in body:
			title = re.split(r'<\/?figcaption[^>]*>', body)[1].replace("'", "''")
		else:
			title = 'Audio'
		title = "'🎵 " + title + "'"
	elif post['original_type'] == 'chat':
		title = "'💬 Chat'"
	elif post['original_type'] == 'link':
		title = "'🔗 " + re.split(r'\[|\]', body_list[0])[1].replace("'", "''") + "'"
	elif post['original_type'] == 'note':
		title = "'❓ Ask'"
	elif post['original_type'] == 'video':
		title = "'🎥 Video'"
	else:
		# if the first element in the post is an H1 heading, use it as the post's title
		first_element = body_list[0]
		if first_element.startswith('#'):
			title = "'" + re.split(r'#|\n', first_element)[1].strip().replace("'", "''") + "'"
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
	file.write(body)
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
[yellow]•[/] Once everything is looking and working as intended, run [reverse]mkdocs build[/] to build your site!

:question_mark: [b]Questions or suggestions?[/] Let me know over on GitHub:

[b]https://github.com/lilacpixel/tumblmark/issues[/]""", 1), border_style='royal_blue1', highlight=True, title=':glowing_star: [b default]Next Steps[/]', title_align='left'))

				print('\n[b]Thank you for trying TumblMark![/] :heart-emoji:\n\nHave a great day! :cat2:\n')
	except KeyboardInterrupt:
		# exit cleanly if interrupt is received
		print('\n\nKeyboard interrupt detected; exiting! :wave:')
		sys.exit(0)

if __name__ == '__main__':
	main()