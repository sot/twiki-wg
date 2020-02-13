# Scrape the SSAWG/Aspect pages for trending images
# and copy them to a separate page for consolidation
# and efficient viewing.

import requests
from bs4 import BeautifulSoup
import jinja2
from urllib import request, response, error, parse
from urllib.request import urlopen
from datetime import datetime, timedelta

print("\n")

# Establish the pages that need to be scraped.
# THE LIST IS NOT COMPLETE.
pages = [
    "kalman_watch/", 
    "acq_stat_reports/",
    "gui_stat_reports/",
    "obc_rate_noise/trending/",
    "perigee_health_plots/",
    # "periscope_drift_reports/",    # This page requires a username/password
]

base_url = "https://cxc.cfa.harvard.edu/mta/ASPECT/"

# Recursive function to get URLs for pages that update
# every month. This removes requirement to *always* look back
# due to month rollovers.
def get_date_pages(reports_page, base_url, day_offset):
    now = str(datetime.now() + timedelta(days=int(day_offset))) 
    year = now[0:4]
    month = now[5:7]
    if reports_page == "perigee_health_plots/":
        temp_url = base_url + page + "SUMMARY_DATA/" + year + "-M" + month + "/"
    else:
        temp_url = base_url + reports_page + year + "/M" + month + "/"
    quick_test = requests.get(temp_url).text
    soup = BeautifulSoup(quick_test, "lxml")
    if soup.title.text == "Missing Page":
        get_date_pages(page,base_url,day_offset-1)
    return temp_url


images = {}

# For all pages, combine with url and necessary
# url path; call it and grab text.
# Then BeautifulSoup for images.
for page in pages:
    if page[-8:-1] == "reports" or page == "perigee_health_plots/":
        url = get_date_pages(page,base_url,10)
    # elif page == "perigee_health_plots/":
    #     url = base_url + page + "SUMMARY_DATA/" + year + "-M" + month + "/"
    else:
        url = base_url + page
    ssawg = requests.get(url).text
    soup = BeautifulSoup(ssawg, "lxml")
    tmp_images = []
    for img in soup.find_all('img'):
        tmp_images.append(img["src"])
    for x in tmp_images:
        for y in x:
            images[url] = tmp_images

# Get PNGs.
# Assumes only PNGs are used for trending
pngs = []
for x in images:
    for y in images[x]:
        if y[-3:] == "png":
            pngs.append(x + y)

for i in pngs:
    print(i)
        