# 📔 TumblMark

Quickly export your original Tumblr posts to a static site with [MkDocs](https://www.mkdocs.org/) and [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/). Keep a local copy for private browsing, or upload as a fully-functional blog to your favorite static web host. Add new pages and posts at any time with your favorite Markdown editor, and keep the posting going! ❤️

TumblMark supports all Tumblr post formats (both legacy and NPF), as well as custom text formatting, asks, reblog chains (self-reblogs only), draft and private posts, and pinned posts ([Material for MkDocs insiders](https://squidfunk.github.io/mkdocs-material/insiders/) only). Additionally, it uses [Bunny Fonts](https://bunny.net/fonts/) for external fonts and youtube-nocookie for YouTube embeds, helping to preserve your and your visitors' privacy.

> **If you find TumblMark useful and want to show your appreciation, you can leave me a tip on Ko-fi.** Thanks so much for your support! 💕
>
> https://ko-fi.com/cariri

## Dependencies

- [Python 3.x](https://www.python.org/downloads/)
- [MkDocs](https://www.mkdocs.org/) + [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)
- [MkDocs-GLightbox](https://github.com/blueswen/mkdocs-glightbox)
- [Markdownify](https://github.com/matthewwithanm/python-markdownify)
- [mdx-truly-sane-lists](https://github.com/radude/mdx_truly_sane_lists)
- [PyTumblr](https://github.com/tumblr/pytumblr)
- [Rich](https://github.com/Textualize/rich)

## Installation

1. To check if Python is installed on your computer, open a terminal and run the following command:

   ```bash
   python --version
   ```

   You should see something like this:

   ```
   Python 3.12.10
   ```

   If you don't see a similar message, or if the listed version is lower than version 3.0, install the appropriate Python package for your computer and operating system from [python.org](https://www.python.org/downloads/).

2. Install the required dependencies:
   ```bash
   pip install mkdocs mkdocs-material mkdocs-glightbox mdx_truly_sane_lists python-markdownify pytumblr rich
   ```

3. Download the latest [release](/releases/latest) from GitHub and extract it.

## Getting started

### Registering an application

To use TumblMark, you'll need to create an application and authenticate with Tumblr's API. Log in to your Tumblr account and navigate to Tumblr's applications page:

https://www.tumblr.com/oauth/apps

Click the **Register application** button, then fill in the following fields:

- **Application Name:** A descriptive name for the application (i.e. `Export Posts`)
- **Application Website:** Any URL that belongs to you, such as your Tumblr URL
- **Application Description:** A short description of the application (i.e. `Tool to export Tumblr posts.`)
- **Administrative contact email:** Your email address
- **Default callback URL:** `http://localhost`
- **OAuth2 redirect URLs:** `http://localhost`

All other fields may be left blank.

After submitting your form, you'll be redirected back to the applications page. You should see the application name that you chose, as well as an **OAuth Consumer Key**. Click the link below this text that reads **Show secret key**. You'll need both of these for the next step.

### Authenticating with the API

Once you've created your application, you'll need to authenticate with the API to obtain a token. This token will grant you full privileges for your Tumblr account, just as if you were logged in on the website. Navigate to the Tumblr API console in your browser:

https://api.tumblr.com/console/

Enter the consumer key and secret key that you obtained in the last step, then click **Authenticate**. Once you've successfully authenticated, click **Show keys** at the top of the page. This will display all of the credentials you'll need, including your consumer key, secret key, token, and token secret.

> [!CAUTION]
>
> Be sure to store your API credentials safely, and don't upload or share them anywhere. Anyone who has your credentials can log into your account and perform operations, just as if they'd logged in with your username and password.

## Usage

1. In your terminal, navigate to the folder that contains `tumblmark.py`.
   ```bash
   cd ./tumblmark
   ```

2. Run the script, with or without arguments (see [Optional arguments](#optional-arguments)):
   ```bash
   ./tumblmark.py
   ```

3. The script will prompt you for your API credentials, as well as the username of the account you'd like to export from. Alternatively, you can create a `credentials.txt` file with your API credentials in the same folder as the script, using the following format:
   ```ini
   [credentials]
   consumer_key = dBFPL8WTnXQEJgetY9fGSxaMAUpNsqk75KHVmRhC4Zy32zc6Dj
   secret = WmJenR7ELqbuCtXkMZ2BTQV9AsGN48gdjrFzDxYhK5SHp3Pa6v
   token = mMet4UPjswHZ5CNuRzB9F2dXWp37LGhn6QyacSJDgbVATkrKEf
   token_secret = NvjCSuAhn9rbYaqt5WZUcKRFgyXexLm7s46pEMVP3kd82fzDBT
   ```

   Credentials provided in this format will be automatically detected by the script.

### Optional arguments

Additional arguments may be added to the export command to modify its behavior.

- **-d** *or* **--draft** - Include draft posts in export.
- **-p** *or* **--private** - Include private posts in export.

**Example:**

To include both draft and private posts in your export:

```bash
./tumblmark.py -d -p
```

## Finishing up

You should have several new folders in your working directory after completing an export. `/posts` will contain all of your exported posts, while `/posts/audio`, `/posts/img`, and `/posts/video` will house any audio, images, or video contained within your posts. (Audio and video hosted on third-party sites, such as Spotify or YouTube, will not be downloaded.) Your posts will be saved in [Markdown](https://www.markdownguide.org/) format, a simple plain-text markup language that's used for basic document formatting.

To preview your site, make sure you're in the directory that contains your site, then run the following command in your terminal:

```bash
mkdocs serve
```

This will build a preview version of your site and serve it on your local machine. Open http://localhost:8000 in your browser, and you'll see your site with your exported posts!

### Customizing settings

At this point, you might want to make some modifications to personalize it a bit. The file `mkdocs.yml` contains all of the settings for your site. You might be interested in making some or all of the following changes.


- Change the name of your site:
  ```yaml
  site_name: Pictures of Cats
  ```

- Change the icon that appears in the top navigation bar:
  ```yaml
  theme:
    icon:
      logo: material/library
  ```

  You can search the library of available icons on Material for MkDocs [here](https://squidfunk.github.io/mkdocs-material/setup/changing-the-logo-and-icons/#logo-icon-bundled) (click the `+` icon next to the example).

- Change the primary and accent colors for light and/or dark mode:
  ```yaml
  theme:
    palette:
      - primary: indigo
        accent: indigo
        scheme: default
  ```

  You can view and test all of the available color options [here](https://squidfunk.github.io/mkdocs-material/setup/changing-the-colors/#primary-color).

  The `default` scheme uses a "light mode" palette. To change the default to dark mode, move the `slate` block, beginning on the line with the hyphen and ending on the line with `name`, to display above the `default` block:
  
  ```yaml
  theme:
    palette:
      - primary: indigo
        accent: indigo
        scheme: slate
        toggle:
          icon: material/brightness-4
          name: Switch to light mode
      - primary: indigo
        accent: indigo
        scheme: default 
        toggle:
          icon: material/brightness-7
          name: Switch to dark mode
  ```
  
  Be sure not to accidentally add or delete any spaces when rearranging blocks!
  
- You can display a custom "avatar" in the sidebar of your site by uncommenting the following lines in `mkdocs.yml`:

  ```yaml
  #extra:
  #  avatar:
  #    file: 'filename.jpg'
  #    alt: 'Alt text for your avatar'
  ```

  Avatar images should be placed in `/docs/img`. A square image of 480x480 pixels is recommended for best results.

For more on how to use and customize your site, check out the documentation for [MkDocs](https://www.mkdocs.org/) and [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/).

### Draft and private posts

If you enabled draft or private posts for your export, you may see some posts marked as `Draft` in your site preview. Both draft and private posts are marked as drafts in the post's front matter:

```markdown
---
date: 2015-04-20T08:30:45
title: 'Post title'
draft: true
---

# Post title

This is the **content** of my post
```

These posts can be viewed in your local preview, but they won't be included when publishing your site. If you'd like to publish a post marked as a draft, simply remove the line `draft: true`. Conversely, to make a published post private, add `draft: true` on a new line in the post's front matter (between the rows of `---` at the top of the post).

### Creating new posts

New posts can be made by creating a new file in the `/posts` directory with the extension `.md`. The post date must be included in the post's front matter. `YYYY-MM-DD` date format is supported, and you may optionally include the time, like so:

```markdown
---
date: 2025-02-14T12:00:00
title: 'A new post'
---

Here's my new post!
```

A number of applications exist for various platforms that support rich-text editing of Markdown files. [Zettlr](https://zettlr.com/) (free) and [Typora](https://typora.io/) (paid with free trial) are two solid cross-platform options to consider.

> [!NOTE]
>
> While post titles exported from Tumblr are exported in single quotes (`'`) for safety, most post titles don't need to follow this convention. (The exception is post titles where the data type is unclear, such as a title made up of only numbers.) If you do choose to wrap your post titles in quotes, make sure that any single quotes used in the title are *doubled* to prevent errors at build time.
>
> ```markdown
> ---
> date: 2025-04-22
> title: 'This post title won''t break anything'
> ---
> ```
>
> Alternatively, post titles containing single quotes can be safely wrapped in double quotes.
>
> ```markdown
> ---
> date: 2025-04-22
> title: "This post title won't break anything"
> ---
> ```

### Building your site

Once you've confirmed that everything is looking and working as expected, you can build your site by running the following command:

```bash
mkdocs build
```

A `/site` subfolder will be created with all of the necessary files for your site. You can upload these files to any web host that supports static sites, such as [Neocities](https://neocities.org/) or [Netlify](https://www.netlify.com/).

## Known issues

- [A bug in MkDocs-GLightbox](https://github.com/blueswen/mkdocs-glightbox/issues/60) currently prevents lightboxes from opening when an image is clicked on the main blog listing or an archive page. Clicking images on single posts works as intended.

## Licensing

This tool is licensed under GNU GPLv3. Full licensing information can be found in [LICENSE](LICENSE).

---

*Thanks for supporting indie developers. Keep on blogging!* 🐈