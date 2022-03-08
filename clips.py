#!/usr/bin/env python3

import os
import random
import sys
import time
import cherrypy


# If this much time has elapsed since the last access (read/write) to
# a clipboard, its contents will be cleared for the next read.
TIMEOUT_SECS = 900

# How many words to use for randomly generated clipboard names. With
# the wordlist we're using, 3 words gives about 38 bits of entropy.
NUM_RANDOM_WORDS = 3


class Clipboard:
    def __init__(self, name):
        self.name = name
        self.text = ""
        self.timestamp = time.time()

    def get(self):
        if self.timestamp + TIMEOUT_SECS <= time.time():
            self.text = ""
        self.timestamp = time.time()
        return self.text

    def set(self, value):
        self.text = value
        self.timestamp = time.time()


clipboards = {}


def read_wordlist():
    dirname = os.path.dirname(os.path.realpath(__file__))
    path = os.path.join(dirname, "wordlist.txt")
    with open(path, "r") as f:
        return f.readlines()


wordlist = read_wordlist()


class ClipsController:
    def do_index(self):
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>clips - copypasta in the cloud</title>
    <style>
        body {
            margin: 0 auto;
            max-width: 40em;
            padding-left: 16px;
            padding-right: 16px;
            font-family: sans-serif;
        }
    </style>
</head>
<body>
    <p>
        clips is a pastebin-like service that makes it easy to copy text
        between devices using just a web browser.
    </p>
    <p>
        To get started, append a clipboard name of your choosing to the URL.
        Your clipboard is only as secure as the name you use. Note that the
        contents are NOT end-to-end encrypted, and are automatically deleted
        after 15 minutes of inactivity.
    </p>
    <p>
        For programmatic access to a clipboard's contents, append /text
        after the clipboard name. POST will write the contents, and GET
        will read it back.
    </p>
    <p>
        <a href="/random">Generate a randomly named clipboard</a>
    </p>
</body>
</html>
"""

    def do_clip(self):
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>clips - copypasta in the cloud</title>
    <style>
        html {
            display: flex;
            width: 100%;
            height: 100%;
        }

        body {
            flex: 1;
            flex-direction: column;
            display: flex;
        }

        #editor {
            flex: 1;
            font-family: monospace;
            font-size: x-large;
            resize: none;
            margin: 4px;
            border: 1px solid;
            border-radius: 0;
        }

        #controls {
            display: flex;
            flex-direction: row;
        }

        #controls > button {
            flex: 1;
            font-size: large;
            margin: 4px;
            padding: 12px;
            border: 1px solid;
            border-radius: 0;
        }
    </style>
    <script>
        window.onload = async function() {
            let editor = document.getElementById("editor");
            let openurl = document.getElementById("openurl");
            let copyclip = document.getElementById("copyclip");

            let name = window.location.pathname.substring(1);
            let texturl = "/" + name + "/text";
            let resp = await fetch(texturl);
            let text = await resp.text();

            editor.placeholder = name;
            editor.value = text;
            editor.addEventListener("input", async function() {
                await fetch(texturl, {
                    method: "POST",
                    headers: {
                        "Content-Type": "text/plain",
                    },
                    body: editor.value,
                });
                openurl.innerText = "Open as URL";
                copyclip.innerText = "Copy to clipboard";
            });

            openurl.addEventListener("click", function() {
                let text = editor.value;
                try {
                    new URL(text);
                } catch (_) {
                    openurl.innerText = "Invalid URL!";
                    return;
                }
                window.open(text, "_blank", "noopener,noreferrer");
                openurl.innerText = "Opened!";
            });

            copyclip.addEventListener("click", function() {
                editor.select();
                document.execCommand("copy");
                editor.blur();
                copyclip.innerText = "Copied!";
            });
        };
    </script>
</head>
<body>
    <textarea id="editor" placeholder="Loading...">
    </textarea>
    <div id="controls">
        <button id="openurl">Open as URL</button>
        <button id="copyclip">Copy to clipboard</button>
    </div>
</body>
</html>
"""

    def do_random(self):
        words = random.sample(wordlist, NUM_RANDOM_WORDS)
        name = "".join(map(str.capitalize, words))
        raise cherrypy.HTTPRedirect("/" + name)

    def get_clipboard(self, name):
        clipboard = clipboards.get(name)
        if clipboard is None:
            clipboard = clipboards[name] = Clipboard(name)
        return clipboard

    def get_text(self, name):
        clipboard = self.get_clipboard(name)
        cherrypy.response.headers["Content-Type"] = "text/plain"
        return clipboard.get()

    def set_text(self, name):
        if cherrypy.request.headers["Content-Type"] != "text/plain":
            raise cherrypy.HTTPError(400)
        text = cherrypy.request.body.read().decode()
        clipboard = self.get_clipboard(name)
        clipboard.set(text)
        return None

    def do_text(self, name):
        if cherrypy.request.method == "GET":
            return self.get_text(name)
        elif cherrypy.request.method == "POST":
            return self.set_text(name)
        else:
            raise cherrypy.HTTPError(405)

    @cherrypy.expose
    def default(self, *segs):
        if len(segs) == 0:
            return self.do_index()
        if len(segs) == 1 and segs[0].lower() == "random":
            return self.do_random()
        if len(segs) == 1:
            return self.do_clip()
        if len(segs) == 2 and segs[1].lower() == "text":
            return self.do_text(segs[0].lower())
        raise cherrypy.HTTPError(404)


def main():
    port = 80
    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    cherrypy.config.update({
        "server.socket_host": "0.0.0.0",
        "server.socket_port": port,
    })

    config = {
        "/": {
        }
    }

    cherrypy.tree.mount(ClipsController(), "/", config)
    cherrypy.engine.start()
    cherrypy.engine.block()


if __name__ == "__main__":
    main()
