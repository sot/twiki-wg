# --------------------------------------------------
# Scrape the SSAWG/Aspect pages for trending data
# and copy them to a separate page for consolidation
# and efficient viewing.
# ---------------------------------------------------

import requests
import netrc
import argparse
import Ska.ftp
from bs4 import BeautifulSoup
from urllib import request, response, error, parse
from urllib.request import urlopen
from datetime import datetime, timedelta
import Chandra.Time
import re


# ------------------------------------
# Setup for password-protected site(s)
# ------------------------------------

netrc = Ska.ftp.parse_netrc()
if 'https://cxc.cfa.harvard.edu' not in netrc:
    raise RuntimeError('must have authentication in .netrc')

user = netrc['https://cxc.cfa.harvard.edu']['login']
password = netrc['https://cxc.cfa.harvard.edu']['password']

# -----------------------------------
# ESTABLISH BASE URL, TRENDING PAGES
# AND CREATE PROPER URLS TO USE
# -----------------------------------

base_url = "https://cxc.cfa.harvard.edu/mta/ASPECT/"

trending_pages = [
    "kalman_watch/", 
    "acq_stat_reports/",
    "gui_stat_reports/",
    "perigee_health_plots/",
    "periscope_drift_reports/", # this page requires a username/password
    "obc_rate_noise/trending/",
    "fid_drift/",
    "aimpoint_mon/",
    "celmon/",
    "vv_rms/",
    "attitude_error_mon/",
    "fss_check3/"
]


def proper_url(page, base_url):
    if page[-8:-1] == "reports": # conditional to perfrom unique checks on acq/gui stat reports
        for offset in range(4, 0, -1):
            year = (datetime.now()).year
            url = (f'{base_url}{page}{year}/Q{offset}/index.html') # creates the temporary url; will later need '/index.html' removed
            if page == "periscope_drift_reports/": # this page requires a username/password
                page_request = requests.get(url, auth=(user, password))
            else:
                page_request = requests.get(url)
            if page_request.status_code < 300: # verify successful page
                soup = BeautifulSoup(page_request.text, "lxml")  
                temp_tables = soup.find_all('table') # locate table with quarterly dates
                start_time = temp_tables[1].text[12:34] # quarterly start date
                stop_time = temp_tables[1].text[34:] # quarterly stop date
                stop_minus_start = Chandra.Time.date2secs(stop_time) - Chandra.Time.date2secs(start_time)
                halfway = Chandra.Time.date2secs(start_time) + stop_minus_start
                if Chandra.Time.date2secs(datetime.now()) > halfway: # if 50% through quarter
                    return (f'{base_url}{page}{year}/Q{offset}/')
                elif offset == 1: # if it's the first quarter of the year
                    return (f'{base_url}{page}{year-1}/Q4/') # switch to fourth quarter of previous year
                else:
                    return (f'{base_url}{page}{year}/Q{offset-1}/') # try previous quarter
            else:
                continue
    elif page ==  "perigee_health_plots/": # perform unique checks on this page
        for offset in range(0, -31, -1): # looks back one month
            now = datetime.now() + timedelta(days=(offset))
            if now.day > 15: # if roughly halfway through the month
                year = now.year
                month = now.month
                url = (f'{base_url}{page}SUMMARY_DATA/{year}-M{month:02}/') # provides URL if halfway through month
                response = requests.get(url)
                if response.status_code >= 300:
                    continue
                else:
                    quick_check = requests.get(url).text
                    soup = BeautifulSoup(quick_check, "lxml")
                    if soup.title.text != "Missing Page":
                        return url
            else: # if not halfway through the month, get previous month
                now = datetime.now() + timedelta(days=-16) # offset of -16 days will get previous month
                year = now.year
                month = now.month
                url = (f'{base_url}{page}SUMMARY_DATA/{year}-M{month:02}/')
                response = requests.get(url)
                if response.status_code < 300:
                    return url
                else:
                    continue
    else:
        return base_url + page

# -----------------------------
# GET VARIOUS HTML INFORMATION
# -----------------------------

def get_images(soup,url):
    images = {}
    for img in soup.find_all('img'):
        if img['src'][-3:] == "png" or img['src'][-3:] == "gif": # look for all pngs and gifs
            new_image_url = f"<img src ='{url}{img['src']}'>"
            images[img['src']] = new_image_url
    return(images)
   
def get_title(soup,url):
    title_text = [title for title in soup.find_all('title')]
    return title_text
 
def get_headers2(soup,url):
    header2_text = [header2 for header2 in soup.find_all('h2')]
    return header2_text
 
def get_headers3(soup,url):
    header3_text = [header3 for header3 in soup.find_all('h3')]
    return header3_text

def get_headers4(soup,url):
    header4_text = [header4 for header4 in soup.find_all('h4')]
    return header4_text

def get_tables(soup,identifier, url):
    tables = [table for table in soup.find_all('table')]
    new_tables = [str(table) for table in tables]
    for index, table in enumerate(new_tables):    
            new_tables[index] = re.sub("src=\"", "src=\"" + url, table) # replace truncated img src url calls with full url calls;
    return new_tables                                                   # this allows the script to be run/tested outside network

def get_paragraph(soup,identifier):
    paragraph = [para for para in soup.find_all('p')]
    return paragraph

def get_anchors(soup,identifier):
    anchors = [anchor for anchor in soup.find_all('a')]
    return anchors

def get_tt(soup, identifier):
    tts = [tt for tt in soup.find_all("tt")]
    return tts

def get_divs(soup, identifier, url):
    divs = [div for div in soup.find_all("div")]
    return divs

def get_ems(soup, identifier):
    ems = [em for em in soup.find_all("em")]
    return ems

def get_scripts(soup, identifier):
    scripts = [scripts for scripts in soup.find_all("script")]
    return scripts

# ---------------------------------
# ESTABLISH HTML INFO FOR EACH PAGE
# ---------------------------------

class Page():
    def __init__(self,page):
        self.identifier = page[0:-1]
        self.page = page
        self.url = proper_url(self.page, base_url)
        if self.page == "periscope_drift_reports/":
            self.url_text = requests.get(self.url, auth=("periscope", "aca")).text
        else:
            self.url_text = requests.get(self.url).text
        self.soup = BeautifulSoup(self.url_text, "lxml")
        self.title = get_title(self.soup,self.url)
        self.images = get_images(self.soup, self.url)
        self.headers2 = get_headers2(self.soup, self.url)
        self.headers3 = get_headers3(self.soup, self.url)
        self.headers4 = get_headers4(self.soup, self.url)
        self.tables = get_tables(self.soup,self.identifier, self.url)
        self.paragraph = get_paragraph(self.soup, self.identifier)
        self.anchors = get_anchors(self.soup, self.identifier)
        self.tts = get_tt(self.soup, self.identifier)
        self.divs = get_divs(self.soup, self.identifier, self.url)
        self.ems = get_ems(self.soup, self.identifier)
        self.scripts = get_scripts(self.soup, self.identifier)
        web_block = {}
        self.web_block = web_block[self.identifier] = {
                                           "URL": self.url,
                                           "HTML_URL": "<a href = " + str(self.url) + "> " + str(self.url)  + "</a>" + "<br>",
                                           "TITLE": self.title,
                                           "IMAGES": self.images,
                                           "HEADERS2": self.headers2,
                                           "HEADERS3": self.headers3,
                                           "HEADERS4": self.headers4,
                                           "TABLES": self.tables,
                                           "PARAGRAPH": self.paragraph,
                                           "ANCHORS": self.anchors,
                                           "TTS": self.tts,
                                           "DIVS": self.divs,
                                           "EMS": self.ems,
                                           "SCRIPTS": self.scripts,
        }


trending_blocks = {}
for trending_page in trending_pages:
    trending_blocks[trending_page[:-1]] = Page(trending_page)
    

# --------------------------------------------
# CREATE CONSOLIDATED BLOCK OF NECESSARY WEB
# INFORMATION IN THE ORDER REQUESTED
# --------------------------------------------

trending_official = {
    trending_blocks["kalman_watch"].identifier:
        [
            trending_blocks["kalman_watch"].web_block['HEADERS2'][0],
            trending_blocks["kalman_watch"].web_block['HTML_URL'],
            trending_blocks["kalman_watch"].web_block['HEADERS3'][0],
            trending_blocks["kalman_watch"].web_block['PARAGRAPH'][1],
            trending_blocks["kalman_watch"].web_block['IMAGES']["kalman_drop_intervals.png"],
            "<br><br>",
            trending_blocks["kalman_watch"].web_block['TABLES'][1],
        ],
    trending_blocks["acq_stat_reports"]:
        [
            trending_blocks["acq_stat_reports"].web_block['HEADERS2'][0],
            trending_blocks["acq_stat_reports"].web_block['HTML_URL'],
            trending_blocks["acq_stat_reports"].web_block['HEADERS3'][0],
            trending_blocks["acq_stat_reports"].web_block['TABLES'][1],
            trending_blocks["acq_stat_reports"].web_block['IMAGES']["id_acq_stars.png"],
            trending_blocks["acq_stat_reports"].web_block['IMAGES']["delta_mag_scatter.png"],
            trending_blocks["acq_stat_reports"].web_block['TABLES'][4],
        ],
    trending_blocks["gui_stat_reports"]:
        [
            trending_blocks["gui_stat_reports"].web_block['HEADERS2'][0],
            trending_blocks["gui_stat_reports"].web_block['HTML_URL'],
            trending_blocks["gui_stat_reports"].web_block['HEADERS3'][0],
            trending_blocks["gui_stat_reports"].web_block['TABLES'][1],
            "<table><tbody><tr><td>",
            trending_blocks["gui_stat_reports"].web_block['IMAGES']["delta_mag_vs_mag.png"],
            "</td><td>",
            trending_blocks["gui_stat_reports"].web_block['IMAGES']["delta_mag_vs_color.png"],
            "</td></tr><tr><td>",
            trending_blocks["gui_stat_reports"].web_block['IMAGES']["frac_not_track_vs_mag.png"],
            "</td><td>",
            trending_blocks["gui_stat_reports"].web_block['IMAGES']["frac_bad_obc_status.png"],
            "</td></tr></tbody></table>",
            trending_blocks["gui_stat_reports"].web_block['TABLES'][4],
        ],
    trending_blocks["perigee_health_plots"]:
        [
            trending_blocks["perigee_health_plots"].web_block['HEADERS3'][0],
            trending_blocks["perigee_health_plots"].web_block['HTML_URL'],
            trending_blocks["perigee_health_plots"].web_block['PARAGRAPH'][0],
            trending_blocks["perigee_health_plots"].web_block['TABLES'][1],
        ],
    trending_blocks["periscope_drift_reports"]:
        [
            trending_blocks["periscope_drift_reports"].web_block['HEADERS2'][0],
            trending_blocks["periscope_drift_reports"].web_block['HTML_URL'],
            trending_blocks["periscope_drift_reports"].web_block['HEADERS3'][0],
            trending_blocks["periscope_drift_reports"].web_block['TABLES'][1],
            trending_blocks["periscope_drift_reports"].web_block['HEADERS3'][1],
            trending_blocks["periscope_drift_reports"].web_block['IMAGES']['drift_histogram.png'],
            trending_blocks["periscope_drift_reports"].web_block['HEADERS3'][2],
            "<table><tbody><tr><td>",
            trending_blocks["periscope_drift_reports"].web_block['IMAGES']['large_drift_ang_y_corr.png'],
            "</td><td>",
            trending_blocks["periscope_drift_reports"].web_block['IMAGES']['large_drift_ang_z_corr.png'],
            "</td></tr></tbody></table>",
        ],
    trending_blocks["obc_rate_noise/trending"]:
        [
            trending_blocks["obc_rate_noise/trending"].web_block['HEADERS2'][0],
            trending_blocks["obc_rate_noise/trending"].web_block['HTML_URL'],            
            trending_blocks["obc_rate_noise/trending"].web_block['IMAGES']["pitch_time_recent.png"],
            trending_blocks["obc_rate_noise/trending"].web_block['IMAGES']["yaw_time_recent.png"],
            trending_blocks["obc_rate_noise/trending"].web_block['IMAGES']["roll_time_recent.png"],
            trending_blocks["obc_rate_noise/trending"].web_block['IMAGES']["pitch_time_longterm.png"],
            trending_blocks["obc_rate_noise/trending"].web_block['IMAGES']["yaw_time_longterm.png"],
            trending_blocks["obc_rate_noise/trending"].web_block['IMAGES']["roll_time_longterm.png"],
        ],
    trending_blocks["fid_drift"]:
        [
            trending_blocks["fid_drift"].web_block['HEADERS2'][0],
            trending_blocks["fid_drift"].web_block['HTML_URL'],
            trending_blocks["fid_drift"].web_block['HEADERS4'][0],
            trending_blocks["fid_drift"].web_block['HEADERS4'][0].next_sibling,
            "<br>",
            trending_blocks["fid_drift"].web_block['IMAGES']["starcheck_telem.png"],
            trending_blocks["fid_drift"].web_block['IMAGES']["drift_acis_s.png"],
        ],
    trending_blocks["aimpoint_mon"]:
        [
            trending_blocks["aimpoint_mon"].web_block['HEADERS2'][0],
            trending_blocks["aimpoint_mon"].web_block['HTML_URL'],
            trending_blocks["aimpoint_mon"].web_block['HEADERS3'][1],
            trending_blocks["aimpoint_mon"].web_block['HEADERS3'][1].next_sibling,
            trending_blocks["aimpoint_mon"].web_block['TTS'][0],
            trending_blocks["aimpoint_mon"].web_block['TTS'][0].next_sibling,
            trending_blocks["aimpoint_mon"].web_block['DIVS'][0],
            trending_blocks["aimpoint_mon"].web_block['SCRIPTS'][0],
            trending_blocks["aimpoint_mon"].web_block['DIVS'][1],
            trending_blocks["aimpoint_mon"].web_block['SCRIPTS'][1],
            trending_blocks["aimpoint_mon"].web_block['HEADERS3'][2],
            trending_blocks["aimpoint_mon"].web_block['HEADERS3'][2].next_sibling,
            trending_blocks["aimpoint_mon"].web_block['EMS'][2],
            trending_blocks["aimpoint_mon"].web_block['EMS'][2].next_sibling,
            trending_blocks["aimpoint_mon"].web_block['ANCHORS'][9],
            trending_blocks["aimpoint_mon"].web_block['ANCHORS'][9].next_sibling,           
            trending_blocks["aimpoint_mon"].web_block['DIVS'][2],
            trending_blocks["aimpoint_mon"].web_block['SCRIPTS'][2],
        ],
    trending_blocks["celmon"]:
        [
            trending_blocks["celmon"].web_block['HEADERS2'][0],
            trending_blocks["celmon"].web_block['HTML_URL'],
            trending_blocks["celmon"].web_block['HEADERS4'][1],
            trending_blocks["celmon"].web_block['PARAGRAPH'][3],
            trending_blocks["celmon"].web_block['PARAGRAPH'][4],
            "<table><tbody><tr><td>",
            trending_blocks["celmon"].web_block['IMAGES']["offsets-ACIS-S.gif"],
            "</td><td>",            
            trending_blocks["celmon"].web_block['IMAGES']["offsets-ACIS-I.gif"],
            "</td></tr><tr><td>",
            trending_blocks["celmon"].web_block['IMAGES']["offsets-HRC-S.gif"],
            "</td><td>",            
            trending_blocks["celmon"].web_block['IMAGES']["offsets-HRC-I.gif"],
            "</td></tr></tbody></table>",
        ],
    trending_blocks["vv_rms"]:
        [
            trending_blocks["vv_rms"].web_block['HEADERS2'][0],
            trending_blocks["vv_rms"].web_block['HEADERS3'][0],
            trending_blocks["vv_rms"].web_block['HTML_URL'],
            "<br><br><table><tbody><tr><td>",
            trending_blocks["vv_rms"].web_block['IMAGES']["hist2d_fig.png"],
            "</td><td>",
            trending_blocks["vv_rms"].web_block['IMAGES']["hist2d_fig_n100.png"],
            "</td></tr></tbody></table>",
        ],
    trending_blocks["attitude_error_mon"]:
        [
            trending_blocks["attitude_error_mon"].web_block['HEADERS2'][0],
            trending_blocks["attitude_error_mon"].web_block['HEADERS2'][0].next_sibling,
            "<br><br>",
            trending_blocks["attitude_error_mon"].web_block['HTML_URL'],
            trending_blocks["attitude_error_mon"].web_block['HEADERS3'][0],
            trending_blocks["attitude_error_mon"].web_block['IMAGES']["one_shot_vs_angle.png"],            
        ],
    trending_blocks["fss_check3"]:
        [
            trending_blocks["fss_check3"].web_block['HEADERS2'][0],
            trending_blocks["fss_check3"].web_block['HTML_URL'],
            "<br>",
            trending_blocks["fss_check3"].web_block['ANCHORS'][1],
            trending_blocks["fss_check3"].web_block['TABLES'][2],          
        ],
}

# --------------------------------------
# EXPORT THROUGH JINJA TRENDING TEMPLATE
# file: trending_template.html
# --------------------------------------

import jinja2
with open('trending_template.html','r') as template_file:
    template_text = template_file.read()
template = jinja2.Template(template_text)
out_html = template.render(trending_official = trending_official)
with open('trending.html', 'w') as trending_file:
    trending_file.write(out_html)
    
