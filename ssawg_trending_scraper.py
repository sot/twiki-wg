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
from pathlib import Path

import requests
import Ska.ftp
from Chandra.Time import DateTime
from astropy.table import Table
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import jinja2


# ------------------------------------
# Setup for password-protected site(s)
# ------------------------------------

NETRC = Ska.ftp.parse_netrc()
if 'periscope_drift_page' not in NETRC:
    raise RuntimeError('must have periscope_drift_page authentication in ~/.netrc')

# -----------------------------------
# Establish base URL, trending pages,
# and create proper URLs to use
# -----------------------------------

URL_ASPECT = "https://cxc.cfa.harvard.edu/mta/ASPECT"


def get_opt():
    parser = argparse.ArgumentParser(description='Make SSAWG trending page')
    parser.add_argument('--data-dir',
                        type=str,
                        default='.',
                        help='Output data directory')

    args = parser.parse_args()

    return args


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
        if img['src'].endswith('.png') or img['src'].endswith("gif"):
            # look for all pngs and gifs
            new_image_url = f'<img src = "{url}{img["src"]}">'
            images[img['src']] = new_image_url
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
class BasePage():
    """
    Base class for establishing page, URL, and HTML information.
    """
    auth = None

    def __init__(self, page):
        self.page = page
        # self.current_url preserves ability to grab data from
        # current urls, versus conditional dates later
        # (e.g. acq stats report - acq ids image)
        self.url, self.current_url = self.get_url()

        # Generate the page requests and verify page is accessible
        self.page_request = self.get_page_request()

        self.url_text = self.page_request.text
        self.soup = BeautifulSoup(self.url_text, "lxml")
        if self.page != "celmon":
            for local_link in self.soup.find_all('a'):
                temp = local_link['href']
                local_link['href'] = self.url + temp

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
            self.current_quarter_acq_images = get_images(self.soup, "img", self.current_url)

        self.tables = get_tables(self.soup, "table", self.url)
        self.url_html = f'<a href = {str(self.url)}>{str(self.url)}</a><br>'

    def get_page_request(self):
        if self.auth:
            page_request = requests.get(self.url, auth=self.auth)
        else:
            page_request = requests.get(self.url)

        if page_request.status_code != 200:
            raise RuntimeError(f'Investigate issues with {self.url}')

        return page_request

    def get_url(self):
        raise NotImplementedError


class GenericPage(BasePage):
    def get_url(self):
        return f'{URL_ASPECT}/{self.page}/', ''


class ReportsPage(BasePage):
    def get_url(self):
        """
        Get the correct URL for the quarterly timeframe; 50% through the quarter.
        """
        for quarter in range(4, 0, -1):
            year = datetime.now().year
            # creates the temporary url; starts at Quarter 4 and works backwards
            url = f'{URL_ASPECT}/{self.page}/{year}/Q{quarter}/'
            # this page requires a username/password
            if self.auth:
                page_request = requests.get(url, auth=self.auth)
            else:
                page_request = requests.get(url)

            if page_request.status_code == 200:
                # use astropy Table
                table_page = (Table.read(page_request.text, format='ascii.html',
                                         htmldict={'table_id': 2}))
                # pull quarterly start and stop dates from page
                start_time = DateTime(table_page['TSTART'][0])
                stop_time = DateTime(table_page['TSTOP'][0])
                # define halfway through the quarter
                halfway = start_time.secs + ((stop_time.secs - start_time.secs) / 2)
                # is now > 50% through quarter?
                if DateTime().secs > halfway:
                    return f'{URL_ASPECT}/{self.page}/{year}/Q{quarter}/', ''
                # if not 50% through and it's the first quarter of the year
                elif quarter == 1:
                    # switch to fourth quarter of previous year
                    return (f'{URL_ASPECT}/{self.page}/{year-1}/Q4/',
                            f'{URL_ASPECT}/{self.page}/{year}/Q{quarter}/')
                else:
                    # try previous quarter
                    return (f'{URL_ASPECT}/{self.page}/{year}/Q{quarter-1}/',
                            f'{URL_ASPECT}/{self.page}/{year}/Q{quarter}/')
            else:
                continue

        raise RuntimeError(f'failed to find URL for {self.page}')


class PeriscopePage(ReportsPage):
    auth = (NETRC['periscope_drift_page']['login'],
            NETRC['periscope_drift_page']['password'])


class PerigeePage(BasePage):
    def get_url(self):
        """
        Get the correct URL for the monthly perigee page; 50% through month.
        """
        now = datetime.now()
        # if ~halfway through the month
        if DateTime().day > 15:
            return f'{URL_ASPECT}/{self.page}/SUMMARY_DATA/{now.year}-M{now.month:02}/', ''
        else:
            last_month = DateTime() - 27
            return (f'{URL_ASPECT}/{self.page}/SUMMARY_DATA/{last_month.year}'
                    f'-M{last_month.mon:02}/', '')


# Get main program options before any other processing
opt = get_opt()

trending_pages = {
    ReportsPage: [
        "acq_stat_reports",
        "gui_stat_reports"],
    PeriscopePage: [
        "periscope_drift_reports"],
    PerigeePage: [
        "perigee_health_plots"],
    GenericPage: [
        "kalman_watch3",
        "obc_rate_noise/trending",
        "fid_drift",
        "aimpoint_mon",
        "celmon",
        "vv_rms",
        "attitude_error_mon",
        "fss_check3",
    ]
}

trending_blocks = {}
for page_class in trending_pages:
    for page in trending_pages[page_class]:
        trending_blocks[page] = page_class(page)


# --------------------------------------------
# Create consolidated block of necessary web
# information in the order requested.
# --------------------------------------------

html_chunks = []

tb = trending_blocks['kalman_watch3']
html_chunks.extend([
    tb.headers2[0],
    tb.url_html,
    tb.headers3[0],
    tb.paragraphs[1],
    tb.divs[0],
    tb.tables[1],
    "<hr>",
])

tb = trending_blocks['acq_stat_reports']
html_chunks.extend([
    trending_blocks["acq_stat_reports"].headers2[0],
    tb.url_html,
    tb.headers3[0],
    tb.tables[1],
    tb.current_quarter_acq_images["id_acq_stars.png"],
    tb.images["delta_mag_scatter.png"],
    tb.tables[4],
    "<hr>",
])

tb = trending_blocks['gui_stat_reports']
html_chunks.extend([
    tb.headers2[0],
    tb.url_html,
    tb.headers3[0],
    tb.tables[1],
    "<table><tbody><tr><td>",
    tb.images["delta_mag_vs_mag.png"],
    "</td><td>",
    tb.images["delta_mag_vs_color.png"],
    "</td></tr><tr><td>",
    tb.images["frac_not_track_vs_mag.png"],
    "</td><td>",
    tb.images["frac_bad_obc_status.png"],
    "</td></tr></tbody></table>",
    tb.tables[4],
    "<hr>",
])

tb = trending_blocks['perigee_health_plots']
html_chunks.extend([
    tb.headers3[0],
    tb.url_html,
    tb.paragraphs[0],
    tb.tables[1],
    "<hr>",
])

tb = trending_blocks['periscope_drift_reports']
html_chunks.extend([
    tb.headers2[0],
    tb.url_html,
    tb.headers3[0],
    tb.tables[1],
    tb.headers3[1],
    tb.images['drift_histogram.png'],
    tb.headers3[2],
    "<table><tbody><tr><td>",
    tb.images['large_drift_ang_y_corr.png'],
    "</td><td>",
    tb.images['large_drift_ang_z_corr.png'],
    "</td></tr></tbody></table>",
    "<hr>",
])

tb = trending_blocks['obc_rate_noise/trending']
html_chunks.extend([
    tb.headers2[0],
    tb.url_html,
    '<br>',
    tb.headers2[0].next_sibling,
    '<br><br>',
    tb.images["pitch_time_recent.png"],
    tb.images["yaw_time_recent.png"],
    tb.images["roll_time_recent.png"],
    tb.images["pitch_time_longterm.png"],
    tb.images["yaw_time_longterm.png"],
    tb.images["roll_time_longterm.png"],
    "<hr>",
])

tb = trending_blocks['fid_drift']
html_chunks.extend([
    tb.headers2[0],
    tb.url_html,
    tb.headers4[0],
    tb.headers4[0].next_sibling,
    "<br>",
    tb.images["starcheck_telem.png"],
    tb.images["drift_acis_s.png"],
    "<hr>",
])

tb = trending_blocks['aimpoint_mon']
html_chunks.extend([
    tb.headers2[0],
    tb.url_html,
    tb.headers3[1],
    tb.headers3[1].next_sibling,
    tb.tts[0],
    tb.tts[0].next_sibling,
    tb.divs[0],
    tb.scripts[0],
    tb.divs[1],
    tb.scripts[1],
    tb.headers3[2],
    tb.headers3[2].next_sibling,
    tb.ems[2],
    tb.ems[2].next_sibling,
    tb.anchors[9],
    tb.anchors[9].next_sibling,
    tb.divs[2],
    tb.scripts[2],
    "<hr>",
])

tb = trending_blocks['celmon']
html_chunks.extend([
    tb.headers2[0],
    tb.url_html,
    tb.headers4[1],
    tb.paragraphs[3],
    tb.paragraphs[4],
    "<table><tbody><tr><td>",
    tb.images["offsets-ACIS-S.gif"],
    "</td><td>",
    tb.images["offsets-ACIS-I.gif"],
    "</td></tr><tr><td>",
    tb.images["offsets-HRC-S.gif"],
    "</td><td>",
    tb.images["offsets-HRC-I.gif"],
    "</td></tr></tbody></table>",
    "<hr>",
])

tb = trending_blocks['vv_rms']
html_chunks.extend([
    tb.headers2[0],
    tb.headers3[0],
    tb.url_html,
    "<br><br><table><tbody><tr><td>",
    tb.images["hist2d_fig.png"],
    "</td><td>",
    tb.images["hist2d_fig_n100.png"],
    "</td></tr></tbody></table>",
    "<hr>",
])

tb = trending_blocks['attitude_error_mon']
html_chunks.extend([
    tb.headers2[0],
    tb.headers2[0].next_sibling,
    "<br><br>",
    tb.url_html,
    tb.headers3[0],
    tb.images["one_shot_vs_angle.png"],
    tb.headers3[1],
    tb.paragraphs[1],
    "<br><br><table><tbody><tr><td>",
    tb.images["roll_err_vs_time.png"],
    "</td><td>",
    tb.images["roll_err_hist.png"],
    "</td></tr><tr><td>",
    tb.images["point_err_vs_time.png"],
    "</td><td>",
    tb.images["point_err_hist.png"],
    "</td></tr></tbody></table>",
    "<hr>",
])

tb = trending_blocks['fss_check3']
html_chunks.extend([
    tb.headers2[0],
    tb.url_html,
    "<br>",
    tb.anchors[1],
    tb.tables[2],
    "<hr>",
])


# --------------------------------------
# Export through Jinja trending template
# file: trending_template.html
# --------------------------------------

data_dir = Path(opt.data_dir)

with open(data_dir / 'ssawg_trending_template.html', 'r') as fh:
    template_text = fh.read()
template = jinja2.Template(template_text)
out_html = template.render(html_chunks=html_chunks)
with open(data_dir / 'ssawg_trending.html', 'w') as trending_file:
    trending_file.write(out_html)
