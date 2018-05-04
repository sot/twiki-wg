#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import bs4
import Ska.ftp
import re


aspect_url = 'https://occweb.cfa.harvard.edu/twiki/bin/view/Aspect/'
meeting_index_page = 'StarWorkingGroup'
agendas_filename = 'agendas.html'
MIN_DATE = '2009x01x01'

netrc = Ska.ftp.parse_netrc()
if 'occweb' not in netrc:
    raise RuntimeError('must have occweb auth in ~/.netrc')

user = netrc['occweb']['login']
password = netrc['occweb']['password']


def get_twiki_page(page):
    """
    Get and parse a TWiki page.
    """
    print('Reading {} twiki page'.format(page))
    r = requests.get(aspect_url + page, auth=(user, password))
    soup = bs4.BeautifulSoup(r.text, 'lxml')
    return soup


def get_list_after(tag, name, text):
    """
    Find <ul> content after ``name`` tag that has ``text``.
    """
    for content_tag in tag.find_all(name):
        if re.search(text, content_tag.text, re.IGNORECASE):
            break
    else:
        raise ValueError('no matching tag found')

    list_tag = content_tag.find_next('ul')
    if list_tag is None:
        raise ValueError('no list found: {}'.format(content_tag))

    return list_tag


def find_tag(tag, name, text):
    """
    Find first ``name`` tag with ``text``
    """
    for content_tag in tag.find_all(name):
        if re.search(text, content_tag.text, re.IGNORECASE):
            return content_tag


# The output of this process is a summary page named ``agendas_filename`` with
# all the agenda sections glopped together.  First read and parse the existing
# page.
agendas_page = bs4.BeautifulSoup(open(agendas_filename).read(), 'lxml')
agendas_index = agendas_page.find('div', id='ssawg_agendas')

# Remove the last two meetings to force reprocessing of those (e.g. if
# content gets updated post-meeting).
re_ssawg = re.compile('StarWorkingGroupMeeting2\d\d\d')
agenda_divs = agendas_index.find_all('div', id=re_ssawg)
for agenda_div in agenda_divs[:2]:
    agenda_div.extract()

# Get the main WG meeting index page with a <ul> list that looks like
# below within an H2 section 'Meeting Notes':
# * StarWorkingGroupMeeting2018x05x16
# * StarWorkingGroupMeeting2018x05x02
# * StarWorkingGroupMeeting2018x04x18

meeting_index = get_twiki_page(meeting_index_page)
meetings = find_tag(meeting_index, 'h2', 'Meeting Notes')

# Narrow down to the list (UL) of links to meeting notes
meeting_list = meetings.find_next(name='ul')

# Find all the HREF links that are not already in the agendas_index
links = meeting_list.find_all('a')
links = [link for link in links
         if link.text > 'StarWorkingGroupMeeting' + MIN_DATE]

new_links = [link for link in links
             if not agendas_index.find('div', id=link.text)]

# Step through each new meeting notes page and grab the agenda section.
# Insert this as a new <div> section and give it an id for future
# reference along with an <h2> title.
for ii, new_link in enumerate(reversed(new_links)):
    meeting = new_link.text  # e.g. StarWorkingGroupMeeting2017x07x12
    meeting_page = get_twiki_page(meeting)
    try:
        meeting_agenda_ul = get_list_after(meeting_page, 'h2', r'Agenda')
    except:
        meeting_agenda_ul = 'No agenda'

    # Make the new <div> with an enclosed <h2> plus agenda items
    agenda_div = agendas_page.new_tag('div', id=meeting)
    agenda_a = agendas_page.new_tag('a', href=new_link['href'])
    agenda_a.append(new_link.text[-10:])
    agenda_h2 = agendas_page.new_tag('h2')
    agenda_h2.append(agenda_a)
    agenda_div.append(agenda_h2)
    agenda_div.append(meeting_agenda_ul)

    for tag in agenda_div.find_all('a'):
        if tag['href'].startswith('/twiki'):
            tag['href'] = 'https://occweb.cfa.harvard.edu' + tag['href']

    # Insert the new meeting entry at the front of the agendas_index
    agendas_index.insert(0, agenda_div)

    if ii % 5 == 0:
        print('Writing to {}'.format(agendas_filename))
        with open(agendas_filename, 'w') as f:
            f.write(agendas_page.prettify())


with open(agendas_filename, 'w') as f:
    f.write(agendas_page.prettify())
