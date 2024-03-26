#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

"""
Creates a consolidated SSAWG trending page.

Scrapes SSAWG trending pages and creates a
sngle page for efficient viewing.

Usage::
    $ python ssawg_trending_scraper.py ...
"""
import argparse
import html
import re
import time
import traceback
from pathlib import Path

import astropy.units as u
import jinja2
import requests
import ska_ftp
from astropy.table import Table
from bs4 import BeautifulSoup
from cxotime import CxoTime

# ------------------------------------
# Setup for password-protected site(s)
# ------------------------------------

NETRC = ska_ftp.parse_netrc()
if "periscope_drift_page" not in NETRC:
    raise RuntimeError("must have periscope_drift_page authentication in ~/.netrc")

# -----------------------------------
# Establish base URL, trending pages,
# and create proper URLs to use
# -----------------------------------

URL_ASPECT = "https://cxc.cfa.harvard.edu/mta/ASPECT"


def get_opt():
    parser = argparse.ArgumentParser(description="Make SSAWG trending page")
    parser.add_argument(
        "--data-dir", type=str, default=".", help="Output data directory"
    )
    return parser


def get_elements(soup, element):
    """
    Grab various elements from page.
    """
    return list(soup.find_all(element))


def get_images(soup, image, url):
    """
    Find all pngs and gifs.
    """
    images = {}
    for img in soup.find_all(image):
        if img["src"].endswith(".png") or img["src"].endswith("gif"):
            # look for all pngs and gifs
            new_image_url = f'<img src = "{url}{img["src"]}" style="max-width:800px">'
            images[img["src"]] = new_image_url
    return images


def get_tables(soup, tbl, url):
    """
    Find all tables.
    """
    tables = [table for table in soup.find_all(tbl)]
    new_tables = [str(table) for table in tables]
    for index, table in enumerate(new_tables):
        # replace truncated img src url calls with full url calls;
        # this allows the script to be run/tested outside network
        new_tables[index] = re.sub('src="', f'src="{url}/', str(table))
    return new_tables


# ---------------------------------
# Establish HTML info for each page
# ---------------------------------
class BasePage:
    """
    Base class for establishing page, URL, and HTML information.
    """

    page = None
    auth = None
    page_classes = []

    def __init_subclass__(cls, *args, **kwargs) -> None:
        if cls.page is not None:
            BasePage.page_classes.append(cls)
            super().__init_subclass__(*args, **kwargs)

    def parse_page(self):
        # self.current_url preserves ability to grab data from
        # current urls, versus conditional dates later
        # (e.g. acq stats report - acq ids image)
        self.url, self.current_url = self.get_url()
        self.url_html = f"<a href = {str(self.url)}>{str(self.url)}</a><br>"

        # Generate the page requests and verify page is accessible
        self.page_request = self.get_page_request()

        self.url_text = self.page_request.text
        self.soup = BeautifulSoup(self.url_text, "lxml")
        if self.page != "celmon":
            for local_link in self.soup.find_all("a"):
                temp = local_link["href"]
                local_link["href"] = self.url + temp

        # Get various element types
        self.titles = get_elements(self.soup, "title")
        self.headers2 = get_elements(self.soup, "h2")
        self.headers3 = get_elements(self.soup, "h3")
        self.headers4 = get_elements(self.soup, "h4")
        self.paragraphs = get_elements(self.soup, "p")
        self.anchors = get_elements(self.soup, "a")
        self.tts = get_elements(self.soup, "tt")
        self.divs = get_elements(self.soup, "div")
        self.ems = get_elements(self.soup, "em")
        self.scripts = get_elements(self.soup, "script")
        self.images = get_images(self.soup, "img", self.url)
        if self.page == "acq_stat_reports":
            self.current_quarter_acq_images = get_images(
                self.soup, "img", self.current_url
            )

        self.tables = get_tables(self.soup, "table", self.url)

    def get_page_request(self):
        if self.auth:
            page_request = requests.get(self.url, auth=self.auth)
        else:
            page_request = requests.get(self.url)

        if page_request.status_code != 200:
            raise RuntimeError(f"Investigate issues with {self.url}")

        return page_request

    def get_url(self):
        raise NotImplementedError

    def make_html(self):
        raise NotImplementedError


class GenericPage(BasePage):
    def get_url(self):
        return f"{URL_ASPECT}/{self.page}/", ""


class ReportsPage(BasePage):
    def get_url(self):
        """
        Get the correct URL for the quarterly timeframe; 50% through the quarter.
        """
        for quarter in range(4, 0, -1):
            now = CxoTime.now()
            year = now.datetime.year
            # creates the temporary url; starts at Quarter 4 and works backwards
            url = f"{URL_ASPECT}/{self.page}/{year}/Q{quarter}/"
            # this page requires a username/password
            if self.auth:
                page_request = requests.get(url, auth=self.auth)
            else:
                page_request = requests.get(url)

            if page_request.status_code == 200:
                # use astropy Table
                table_page = Table.read(
                    page_request.text, format="ascii.html", htmldict={"table_id": 2}
                )
                # pull quarterly start and stop dates from page
                start_time = CxoTime(table_page["TSTART"][0])
                stop_time = CxoTime(table_page["TSTOP"][0])
                # define halfway through the quarter
                halfway = start_time.secs + ((stop_time.secs - start_time.secs) / 2)
                # is now > 50% through quarter?
                if CxoTime.now().secs > halfway:
                    url = f"{URL_ASPECT}/{self.page}/{year}/Q{quarter}/"
                    return url, url
                # if not 50% through and it's the first quarter of the year
                elif quarter == 1:
                    # switch to fourth quarter of previous year
                    return (
                        f"{URL_ASPECT}/{self.page}/{year-1}/Q4/",
                        f"{URL_ASPECT}/{self.page}/{year}/Q{quarter}/",
                    )
                else:
                    # try previous quarter
                    return (
                        f"{URL_ASPECT}/{self.page}/{year}/Q{quarter-1}/",
                        f"{URL_ASPECT}/{self.page}/{year}/Q{quarter}/",
                    )
            else:
                continue

        raise RuntimeError(f"failed to find URL for {self.page}")


class AcqStatReportsPage(ReportsPage):
    page = "acq_stat_reports"

    def get_html_chunks(self):
        html_chunks = [
            self.headers2[0],
            self.url_html,
            self.headers3[0],
            self.tables[1],
            self.current_quarter_acq_images["id_acq_stars.png"],
            self.images["delta_mag_scatter.png"],
            self.tables[4],
            "<hr>",
        ]
        return html_chunks


class GuiStatReportsPage(ReportsPage):
    page = "gui_stat_reports"

    def get_html_chunks(self):
        html_chunks = [
            self.headers2[0],
            self.url_html,
            self.headers3[0],
            self.tables[1],
            "<table><tbody><tr><td>",
            self.images["delta_mag_vs_mag.png"],
            "</td><td>",
            self.images["delta_mag_vs_color.png"],
            "</td></tr><tr><td>",
            self.images["frac_not_track_vs_mag.png"],
            "</td><td>",
            self.images["frac_bad_obc_status.png"],
            "</td></tr></tbody></table>",
            self.tables[4],
            "<hr>",
        ]
        return html_chunks


class PeriscopePage(ReportsPage):
    page = "periscope_drift_reports"
    auth = (
        NETRC["periscope_drift_page"]["login"],
        NETRC["periscope_drift_page"]["password"],
    )

    def get_html_chunks(self):
        html_chunks = [
            self.headers2[0],
            self.url_html,
            self.headers3[0],
            self.tables[1],
            self.headers3[1],
            self.images["drift_histogram.png"],
            self.headers3[2],
            "<table><tbody><tr><td>",
            self.images["large_drift_ang_y_corr.png"],
            "</td><td>",
            self.images["large_drift_ang_z_corr.png"],
            "</td></tr></tbody></table>",
            "<hr>",
        ]
        return html_chunks


class PerigeePage(BasePage):
    page = "perigee_health_plots"

    def get_url(self):
        """
        Get the correct URL for the monthly perigee page; 50% through month.
        """
        now = CxoTime.now()
        # if ~halfway through the month
        if now.datetime.day > 15:
            return (
                (
                    f"{URL_ASPECT}/{self.page}/SUMMARY_DATA/"
                    f"{now.datetime.year}-M{now.datetime.month:02}/"
                ),
                "",
            )
        else:
            last_month = CxoTime.now() - 27 * u.day
            return (
                f"{URL_ASPECT}/{self.page}/SUMMARY_DATA/{last_month.datetime.year}"
                f"-M{last_month.datetime.month:02}/",
                "",
            )

    def get_html_chunks(self):
        html_chunks = [
            self.headers3[0],
            self.url_html,
            self.paragraphs[0],
            self.tables[1],
            "<hr>",
        ]
        return html_chunks


class WrongBoxAcqAnomPage(GenericPage):
    page = "wrong_box_anom"

    def get_html_chunks(self):
        html_chunks = [
            self.headers2[0],
            self.url_html,
            self.images["wrong_box.png"],
            self.headers4[0],
            self.tables[1],
            "<hr>",
        ]
        return html_chunks


class KalmanWatch3Page(GenericPage):
    page = "kalman_watch3"

    def get_html_chunks(self):
        html_chunks = [
            self.headers2[0],
            self.url_html,
            self.images["mon_win_kalman_drops_-45d_-1d.png"],
            self.headers3[0],
            self.paragraphs[1],
            self.divs[0],
            self.tables[1],
            "<hr>",
        ]
        return html_chunks


class ObcRateNoisePage(GenericPage):
    page = "obc_rate_noise/trending"

    def get_html_chunks(self):
        html_chunks = [
            self.headers2[0],
            self.url_html,
            "<br>",
            self.headers2[0].next_sibling,
            "<br><br>",
            self.images["pitch_time_recent.png"],
            self.images["yaw_time_recent.png"],
            self.images["roll_time_recent.png"],
            self.images["pitch_time_longterm.png"],
            self.images["yaw_time_longterm.png"],
            self.images["roll_time_longterm.png"],
            "<hr>",
        ]
        return html_chunks


class FidDriftPage(GenericPage):
    page = "fid_drift_mon3"

    def get_html_chunks(self):
        html_chunks = [
            self.headers2[0],
            self.url_html,
            self.headers4[0],
            self.headers4[0].next_sibling,
            "<br>",
            self.images["starcheck_telem.png"],
            self.images["drift_acis_s.png"],
            "<hr>",
        ]
        return html_chunks


class AimpointMonPage(GenericPage):
    page = "aimpoint_mon3"

    def get_html_chunks(self):
        html_chunks = [
            self.headers2[0],
            self.url_html,
            self.headers3[1],
            self.headers3[1].next_sibling,
            self.tts[0],
            self.tts[0].next_sibling,
            self.images["observed_aimpoints_dx.png"],
            self.images["observed_aimpoints_dy.png"],
            self.headers3[2],
            self.headers3[2].next_sibling,
            self.ems[1],
            self.ems[1].next_sibling,
            self.ems[1].next_sibling.next_sibling,
            self.ems[1].next_sibling.next_sibling.next_sibling,
            self.images["intra_obs_dy_dz.png"],
            "<hr>",
        ]
        return html_chunks


class CelmonPage(GenericPage):
    page = "celmon"

    def get_html_chunks(self):
        html_chunks = [
            "<h2>Absolute astrometric accuracy</h2>",
            self.url_html,
            self.headers4[1],
            self.paragraphs[1],
            self.paragraphs[5],
            self.images["offsets-ACIS-S-history.png"],
            self.images["offsets-ACIS-I-history.png"],
            self.images["offsets-HRC-S-history.png"],
            self.images["offsets-HRC-I-history.png"],
            "<hr>",
        ]
        return html_chunks


class VvRmsPage(GenericPage):
    page = "vv_rms"

    def get_html_chunks(self):
        html_chunks = [
            self.headers2[0],
            self.headers3[0],
            self.url_html,
            "<br><br><table><tbody><tr><td>",
            self.images["hist2d_fig.png"],
            "</td><td>",
            self.images["hist2d_fig_n100.png"],
            "</td></tr></tbody></table>",
            "<hr>",
        ]
        return html_chunks


class AttitudeErrorMonPage(GenericPage):
    page = "attitude_error_mon"

    def get_html_chunks(self):
        html_chunks = [
            self.headers2[0],
            self.headers2[0].next_sibling,
            "<br><br>",
            self.url_html,
            self.headers3[0],
            self.tables[1],
            self.headers3[1],
            self.paragraphs[1],
            self.tables[2],
            self.headers2[1],
            self.tables[3],
            "<br></br><br></br>",
            "<hr>",
        ]
        return html_chunks


class FssCheck3Page(GenericPage):
    page = "fss_check3"

    def get_html_chunks(self):
        html_chunks = [
            self.headers2[0],
            self.url_html,
            "<br>",
            self.headers3[0],
            self.tables[1],
            "<br>",
            self.headers4[1],
            self.tables[2],
            self.headers4[2],
            self.tables[3],
            "<hr>",
        ]
        return html_chunks


def main(args=None):
    # Get main program options before any other processing
    opt = get_opt().parse_args(args=args)

    html_chunks = []

    for page_class in BasePage.page_classes:
        trend_page = page_class()
        try:
            trend_page.parse_page()
            html_chunks.extend(trend_page.get_html_chunks())
        except Exception:
            html_traceback = html.escape(traceback.format_exc())
            html_chunks.append(
                f"<h2>{trend_page.page}: FAILED PROCESSING</h2>\n"
                f"<pre>\n{html_traceback}\n</pre>\n"
            )

    # --------------------------------------
    # Export through Jinja trending template
    # file: trending_template.html
    # --------------------------------------

    data_dir = Path(opt.data_dir)

    with open(
        Path(__file__).parent / "data" / "ssawg_trending_template.html", "r"
    ) as fh:
        template_text = fh.read()
    template = jinja2.Template(template_text)
    out_html = template.render(html_chunks=html_chunks, update_time=time.ctime())
    with open(data_dir / "ssawg_trending.html", "w") as trending_file:
        trending_file.write(out_html)


if __name__ == "__main__":
    main()
