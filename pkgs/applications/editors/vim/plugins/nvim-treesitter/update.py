#!/usr/bin/env nix-shell
#!nix-shell update-shell.nix -i python

import json
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor
import os
import sys
from os.path import join

log = logging.getLogger("vim-updater")


def generate_grammar(lang, rev, cfg):
    """Generate grammar for a language"""
    info = cfg["install_info"]
    url = info["url"]

    generated = f"""  {lang} = buildGrammar {{
    language = "{lang}";
    version = "0.0.0+rev={rev[:7]}";
    src = """

    generated += subprocess.check_output(["nurl", url, rev, "--indent=4"], text=True)
    generated += ";"

    location = info.get("location")
    if location:
        generated += f"""
    location = "{location}";"""

    if info.get("requires_generate_from_grammar"):
        generated += """
    generate = true;"""

    generated += f"""
    meta.homepage = "{url}";
  }};
"""

    return generated


def update_grammars(nvim_treesitter_dir: str):
    """
    The lockfile contains just revisions so we start neovim to dump the
    grammar information in a better format
    """
    # the lockfile
    cmd = [
        "nvim",
        "--headless",
        "-u",
        "NONE",
        "--cmd",
        f"set rtp^={nvim_treesitter_dir}",
        "+lua io.write(vim.json.encode(require('nvim-treesitter.parsers').get_parser_configs()))",
        "+quit!",
    ]
    log.debug("Running command: %s", ' '.join(cmd))
    configs = json.loads(subprocess.check_output(cmd))

    generated_file = """# generated by pkgs/applications/editors/vim/plugins/nvim-treesitter/update.py

    { buildGrammar, """

    generated_file += subprocess.check_output(["nurl", "-Ls", ", "], text=True)

    generated_file += """ }:

    {
    """

    lockfile_path = os.path.join(nvim_treesitter_dir, "lockfile.json")
    log.debug("Opening %s", lockfile_path)
    with open(lockfile_path) as lockfile_fd:
        lockfile = json.load(lockfile_fd)

        def _generate_grammar(item):
            lang, lock = item
            cfg = configs.get(lang)
            if not cfg:
                return ""
            return generate_grammar(lang, lock["revision"], cfg)

        for generated in ThreadPoolExecutor(max_workers=5).map(
            _generate_grammar, lockfile.items()
        ):
            generated_file += generated
            generated_file += "}\n"
    return generated_file


if __name__ == "__main__":
    generated = update_grammars(sys.args[1])
    open(join(os.path.dirname(__file__), "generated.nix"), "w").write(generated)
