#!/usr/bin/env python

import urllib
import zipfile
import os
import sys
import shutil
import fnmatch
import json
import tempfile
import re
import subprocess
from argparse import ArgumentParser
from contextlib import contextmanager


@contextmanager
def tmpdir():
    name = tempfile.mkdtemp()
    try:
        yield name
    finally:
        shutil.rmtree(name)


def unzip(filename, destination):
    print("Unpacking {}".format(filename))
    zip_ref = zipfile.ZipFile(filename, 'r')
    zip_ref.extractall(destination)
    zip_ref.close()


def download_file(url, destination, filename=None):
    if not filename:
        filename = url.rsplit('/', 1)[-1]
    path = os.path.join(destination, filename)
    if os.path.exists(path):
        print("File %s already exists" % (path))
        sys.exit(1)
    print("Downloading {} to {}".format(url, path))
    urllib.urlretrieve(url, path)
    return path


def download_string(url):
    handle = urllib.urlopen(url)
    return handle.read()


def find_files(root_dir, file_pattern):
    matches = []
    for root, dirnames, filenames in os.walk(root_dir):
        for filename in fnmatch.filter(filenames, file_pattern):
            matches.append(os.path.join(root, filename))
    return matches


def replace_in_file(filename, old, new, flags=None):
    with open(filename) as f:
        if flags is None:
            content = re.sub(old, new, f.read())
        else:
            content = re.sub(old, new, f.read(), flags=flags)

    with open(filename, "w") as f:
        f.write(content)



DOCS_ZIP = "doc-master.zip"
EXAMPLES_ZIP = "examples-master.zip"
BOB_JAR = "bob.jar"


def download():
    if os.path.exists(DOCS_ZIP):
        os.remove(DOCS_ZIP)
    download_file("https://github.com/defold/doc/archive/master.zip", ".", DOCS_ZIP)

    if os.path.exists(EXAMPLES_ZIP):
        os.remove(EXAMPLES_ZIP)
    download_file("https://github.com/defold/examples/archive/master.zip", ".", EXAMPLES_ZIP)

    if os.path.exists(BOB_JAR):
        os.remove(BOB_JAR)
    info = json.loads(download_string("https://d.defold.com/stable/info.json"))
    sha1 = info["sha1"]
    download_file("http://d.defold.com/archive/{}/bob/bob.jar".format(sha1), ".", BOB_JAR)


def process_docs():
    if not os.path.exists(DOCS_ZIP):
        print("File {} does not exists".format(DOCS_ZIP))
        sys.exit(1)

    with tmpdir() as tmp_dir:
        shutil.copyfile(DOCS_ZIP, os.path.join(tmp_dir, DOCS_ZIP))
        unzip(os.path.join(tmp_dir, DOCS_ZIP), tmp_dir)

        print("Processing doc")
        print("...manuals")
        manuals_dir = "manuals"
        if os.path.exists(manuals_dir):
            shutil.rmtree(manuals_dir)
        shutil.copytree(os.path.join(tmp_dir, "doc-master", "docs", "en", "manuals"), manuals_dir)
        for file in find_files(manuals_dir, "*.md"):
            replace_in_file(file, r"({{{?)(.*?)(}}}?)", r"{% raw %}\1\2\3{% endraw %}")
            replace_in_file(file, r"{srcset=.*?}", r"")
            replace_in_file(file, r"::: sidenote(.*?):::", r"<div class='sidenote' markdown='1'>\1</div>", flags=re.DOTALL)
            replace_in_file(file, r"::: important(.*?):::", r"<div class='important' markdown='1'>\1</div>", flags=re.DOTALL)
            replace_in_file(file, r"\((.*?)#_(.*?)\)", r"(\1#\2)")
            replace_in_file(file, r":\[.*?\]\(\.\.\/(.*?)\)", r"{% include \1 %}")

        print("...faq")
        faq_dir = "faq"
        if os.path.exists(faq_dir):
            shutil.rmtree(faq_dir)
        shutil.copytree(os.path.join(tmp_dir, "doc-master", "docs", "en", "faq"), faq_dir)

        print("...shared")
        shared_dir = os.path.join("_includes", "shared")
        if os.path.exists(shared_dir):
            shutil.rmtree(shared_dir)
        shutil.copytree(os.path.join(tmp_dir, "doc-master", "docs", "en", "shared"), shared_dir)

        print("...tutorials")
        tutorials_dir = "tutorials"
        if os.path.exists(tutorials_dir):
            shutil.rmtree(tutorials_dir)
        shutil.copytree(os.path.join(tmp_dir, "doc-master", "docs", "en", "tutorials"), tutorials_dir)
        for file in find_files(tutorials_dir, "*.md"):
            replace_in_file(file, r"({{{?)(.*?)(}}}?)", r"{% raw %}\1\2\3{% endraw %}")

        print("...index")
        index_file = os.path.join("_data", "en.json")
        if os.path.exists(index_file):
            os.remove(index_file)
        shutil.copyfile(os.path.join(tmp_dir, "doc-master", "docs", "en", "en.json"), index_file)

        print("...languages")
        languages_file = os.path.join("_data", "languages.json")
        if os.path.exists(languages_file):
            os.remove(languages_file)
        shutil.copyfile(os.path.join(tmp_dir, "doc-master", "docs", "languages.json"), languages_file)

        print("Done")


def process_examples():
    if not os.path.exists(EXAMPLES_ZIP):
        print("File {} does not exist".format(EXAMPLES_ZIP))
        sys.exit(1)
    if not os.path.exists(BOB_JAR):
        print("File {} does not exist".format(BOB_JAR))
        sys.exit(1)

    with tmpdir() as tmp_dir:
        shutil.copyfile(EXAMPLES_ZIP, os.path.join(tmp_dir, EXAMPLES_ZIP))
        unzip(os.path.join(tmp_dir, EXAMPLES_ZIP), tmp_dir)

        shutil.copyfile(BOB_JAR, os.path.join(tmp_dir, BOB_JAR))

        input_dir = os.path.join(tmp_dir, "examples-master")
        subprocess.call([ "java", "-jar", os.path.join(tmp_dir, BOB_JAR), "--archive", "--platform", "js-web", "resolve", "distclean", "build", "bundle" ], cwd=input_dir)

        examples_dir = "examples"
        if os.path.exists(examples_dir):
            shutil.rmtree(examples_dir)
        shutil.copytree(os.path.join(input_dir, "build", "default", "Defold-examples"), examples_dir)


parser = ArgumentParser()
parser.add_argument('commands', nargs="+", help='Commands (download, docs, examples, help)')
args = parser.parse_args()

help = """
COMMANDS:
download = Download docs, examples and bob.jar
docs = Process the docs (manuals, tutorials and faq)
examples = Build the examples
"""

for command in args.commands:
    if command == "help":
        parser.print_help()
        print(help)
        sys.exit(0)

    if command == "download":
        download()

    if command == "docs":
        process_docs()

    if command == "examples":
        process_examples()
