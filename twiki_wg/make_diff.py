"""Script to compare two TWiki pages and create a GitHub Gist diff page.

Use ``twiki_make_diff --help`` for usage.

By-hand process for reference and for guiding CoPilot:

- Go to the version N-1 view of the guideline.
- Select Raw View at the bottom.
- Copy-all within the window showing the raw TWiki markdown.
- Paste this to a file e.g. prev.twiki. On Mac this can be done with pbpaste >
  prev.twik.
- Repeat this for version N (save to new.twiki).
- Within Ska: pandoc -f twiki -t gfm -o prev.md prev.twiki and pandoc -f twiki -t gfm -o
  new.md new.twiki
- Create a new gist (go to https://github.com and then there is a + dropdown menu and a
  New Gist option
- Paste the prev.md content and name the file (e.g. guideline_acis_fp.md). On Mac pbcopy
  < prev.md helps. Save this as a secret gist.
- Up top there is an Edit button, click that.
- Select all, then paste the content from new.md. Save this.
- Now click on Revisions in the upper left. In the upper right of the diffs there is a
  folded page icon, click that to display the rich diff.
- Copy the URL.
- This URL is tied to a user account so would not serve as a permanent archive of the
  diff, but at least for showing at MPCWG or FDB it could work.

"""

import argparse
import subprocess
from typing import Optional

from bs4 import BeautifulSoup
from kadi.occweb import get_occweb_page

doc = r"""Script to compare two TWiki pages and create a GitHub Gist diff page.

This script requires a GitHub account and the `gh` command line tool
(https://cli.github.com/). In addition you must be logged in to `gh` with `gh auth
login`.

You also need to have authentication to OCCweb set up with a ``~/.netrc`` file. See:
https://sot.github.io/kadi/commands_states.html#initial-setup

After running the script, the URL of the diff page will be printed. This URL is tied to
a user account so would not serve as a permanent archive of the diff, but at least for
showing at MPCWG or FDB it could work. In addition you can save the diff page as an
HTML file using your browser.

Examples
--------
Diff between the latest revision of a dev and release version of a guideline:

  $ ska_twiki_diff \
    --page1 Constraints/MPGuidelines/Development/HighIRZoneGuideline092822 \ --page2
    Constraints/MPGuidelines/Release/GuidelineHighIRZone

Diff between two revisions of a guideline:

  $ ska_twiki_diff \
    --page1 Constraints/MPGuidelines/Release/GuidelineHighIRZone --rev1 2 --rev2 3
"""


def get_argparser():
    argparser = argparse.ArgumentParser(prog="twiki_make_diff", usage=doc)
    argparser.add_argument(
        "--page1",
        help="TWiki page previous version"
        " (e.g. Constraints/MPGuidelines/Release/GuidelineHighIRZone)",
    )
    argparser.add_argument(
        "--page2", help="TWiki page updated version (defaults to same page)"
    )
    argparser.add_argument("--rev1", default="1", help="Previous revision")
    argparser.add_argument("--rev2", default="2", help="Updated revision")
    return argparser


def get_twiki_page_markdown(page: str, rev: Optional[int] = None) -> str:
    """Get raw TWiki page text.

    Parameters
    ----------
    page : str
        TWiki page name (e.g. Constraints/MPGuidelines/Release/GuidelineHighIRZone)
    rev : int, optional
        Revision number (default=latest)

    Returns
    -------
    text : str
        Raw TWiki page markdown text
    """
    page = page.strip("/")
    params = ["raw=on"]
    if rev is not None:
        params.append(f"rev={rev}")
    url = f"https://occweb.cfa.harvard.edu/twiki/bin/view/{page}?{'&'.join(params)}"

    html = get_occweb_page(url)

    bs = BeautifulSoup(html, "html.parser")
    textarea = bs.find_all("textarea")[0]
    text = textarea.get_text()

    return text


def main():
    args = get_argparser().parse_args()

    page1 = args.page1
    page2 = args.page2 or page1
    rev1 = args.rev1
    rev2 = args.rev2
    filename = page1.split("/")[-1] + ".md"

    text_tw = {}
    text_tw[1] = get_twiki_page_markdown(page1, rev1)
    text_tw[2] = get_twiki_page_markdown(page2, rev2)

    # Convert from TWiki to GitHub-flavored markdown. The subprocess commands use byte
    # strings as input and output.
    bytes_md = {}
    for rev, text in text_tw.items():
        bytes_md[rev] = subprocess.check_output(
            ["pandoc", "-f", "twiki", "-t", "gfm"],
            input=text.encode(),
        )

    # Create a new gist using gh CLI starting with the first markdown. The output
    # contains the URL of the gist.
    desc = f"Diff of {page1} rev {rev1} to {page2} rev {rev2}"
    out = subprocess.check_output(
        ["gh", "gist", "create", "-", "--filename", filename, "--desc", desc],
        input=bytes_md[1],
    )
    url = out.decode().strip()

    # Edit the gist to update to the second markdown
    out = subprocess.check_output(
        ["gh", "gist", "edit", url, "-", "--filename", filename],
        input=bytes_md[2],
    )

    print()
    print(f"Created gist {url}")
    print()
    print("To save the diff as a PDF for the record for a meeting (FDB, MPCWG):")
    print("- Navigate to:")
    print(f"    {url}/revisions")
    print(
        "- Click on the earmarked page icon by the ··· (upper right) "
        "to see the rich diff."
    )
    print("- Print to PDF from your browser.")


if __name__ == "__main__":
    main()
