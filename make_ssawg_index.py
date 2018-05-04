#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import argparse
import requests
import bs4
import Ska.ftp
import re


aspect_url = 'https://occweb.cfa.harvard.edu/twiki/bin/view/Aspect/'
meeting_index_page = 'StarWorkingGroup'

netrc = Ska.ftp.parse_netrc()
if 'occweb' not in netrc:
    raise RuntimeError('must have occweb auth in ~/.netrc')

user = netrc['occweb']['login']
password = netrc['occweb']['password']

# Dummy soup for making new tags
soup = bs4.BeautifulSoup('', 'lxml')


def get_twiki_page(page):
    """
    Get and parse a TWiki page.
    """
    print('Reading {} twiki page'.format(page))
    r = requests.get(aspect_url + page, auth=(user, password))
    out = bs4.BeautifulSoup(r.text, 'lxml')

    return out


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


def get_other_notebooks(agenda_div, meeting_page):
    """
    Get links to jupyter notebooks which are within the meeting page
    but NOT already in the main agenda.
    """
    # Notebooks within the new agenda_div
    agenda_nbs = {}
    for tag in agenda_div.find_all('a'):
        if tag.get('href', '').endswith('.ipynb'):
            agenda_nbs[tag['href']] = tag

    # All notebooks
    all_nbs = {}
    for tag in meeting_page.find_all('a'):
        if tag.get('href', '').endswith('.ipynb'):
            all_nbs[tag['href']] = tag

    other_nbs = []
    for href, tag in all_nbs.items():
        if href not in agenda_nbs:
            other_nbs.append((href, tag))

    if other_nbs:
        out = soup.new_tag('div')

        h3 = soup.new_tag('h3')
        h3.string = 'Additional notebooks in meeting notes'
        out.append(h3)

        ul = soup.new_tag('ul')
        for href, tag in other_nbs:
            li = soup.new_tag('li')
            li.append(tag)
            ul.append(li)
        out.append(ul)

    else:
        out = None

    return out


def get_opt():
    parser = argparse.ArgumentParser(description='Make SSAWG index page')
    parser.add_argument('--data-dir',
                        type=str,
                        default='.',
                        help='Output data directory')
    parser.add_argument('--agendas-file',
                        type=str,
                        default='ssawg_index.html',
                        help='Output agendas HTML file')
    parser.add_argument('--start',
                        default='2018x01x01',
                        type=str,
                        help='Start date in TWiki format e.g. 2009x01x01')
    parser.add_argument('--stop',
                        type=str,
                        help='Stop date')
    args = parser.parse_args()
    return args


def main():
    # The output of this process is a summary page named ``agendas_filename`` with
    # all the agenda sections glopped together.  First read and parse the existing
    # page.
    opt = get_opt()

    agendas_filename = os.path.join(opt.data_dir, opt.agendas_file)
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
             if link.text > 'StarWorkingGroupMeeting' + opt.start]

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
        agenda_div = soup.new_tag('div', id=meeting)

        # Make the H2 meeting tag with link to original SSAWG meeting notes
        agenda_h2 = soup.new_tag('h2')
        agenda_a = soup.new_tag('a', href=new_link['href'], target='_blank')
        agenda_a.append(new_link.text[-10:])
        agenda_h2.append(agenda_a)

        agenda_div.append(agenda_h2)
        agenda_div.append(meeting_agenda_ul)

        # Jupyter notebooks in meeting page but not already in agenda section
        other_nbs_div = get_other_notebooks(agenda_div, meeting_page)
        if other_nbs_div:
            agenda_div.append(other_nbs_div)

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


if __name__ == '__main__':
    main()
