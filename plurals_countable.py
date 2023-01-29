# -*- coding: utf-8 -*-
# Author: Anjing Wang
# Date:   Jan-20-2023

# Plurals-and-Countable by Dictionary.video is licensed under
# a Creative Commons Attribution-ShareAlike 4.0 International License. 
# Permissions beyond the scope of this license may be available
# by contacting us at admin@dictionary.video. Full text of 
# the Creative Commons Attribution-ShareAlike 4.0 International License
# can be found at: http://creativecommons.org/licenses/by-sa/4.0/legalcode

import os
import unicodedata
import requests
import re
import inflect
import logging
import time
import pandas as pd

logging.basicConfig(level=logging.INFO)

WHP_NCT_COUNTABLE = 'countable'
WHP_NCT_UNCOUNTABLE = 'uncountable'
WHP_NCT_EITHER = 'either'
WHP_NCT_UNKNOWN = 'unknown'

# -----------------------------------------------------------------------------
# Helper functions
def str_normalize_whitespace(mystring):
    return ' '.join(mystring.split())

def str_merge_whitespaces(mystring):
    mystring = mystring.strip()  # the while loop will leave a trailing space,
                                 # so the trailing whitespace must be dealt with
                                 # before or after the while loop
    while '  ' in mystring:
        mystring = mystring.replace('  ', ' ')
    return mystring

def preprocess_text(txt, keep_line_breaker = True):
    # we can also replace, but unicode lib is a much better way
    # x['text'] = x['text']replace(u'\xa0', u' ')
    txt = unicodedata.normalize('NFKD', txt)
    if keep_line_breaker:
        return str_merge_whitespaces(txt)
    else:
        return str_normalize_whitespace(txt)

# -----------------------------------------------------------------------------
# webster look-up
def webster_find_h1_word(text):
    # pattern: <h1 class="hword">foot</h1>
    h1_word = re.findall(r'<h1 class="hword">(.*?)</h1>', text)

    if len(h1_word) > 0:
        return h1_word[0]
    else:
        return None

# webster does not recognize this word or it's mispelled
def webster_is_mispelled(web_src):
    # <h1 class="mispelled-word">&ldquo;duckss&rdquo;</h1>
    if web_src.find('<h1 class="mispelled-word">') != -1:
        return True
    else:
        return False

def webster_lookup(noun_lookup):
    noun_lookup = noun_lookup.strip()
    # faux pas is a noun, so it is not one word noun anymore
    # if ' ' in noun_lookup:
    #     return None
    noun_lookup = noun_lookup.replace(' ', '%20')
    url = 'https://www.merriam-webster.com/dictionary/%s' % noun_lookup
    response = requests.get(url)
    if response.status_code != 200:
        logging.error(url + ' response: status_code[%d]' % response.status_code)
        return None
    
    page_src = response.text
    # remove all line breaker
    # https://stackoverflow.com/questions/16566268/remove-all-line-breaks-from-a-long-string-of-text
    # page_src = page_src.replace('\n', ' ').replace('\r', '')
    page_src = preprocess_text(page_src, keep_line_breaker = False)

    if webster_is_mispelled(page_src):
        return None

    # what we lookup is already a plural, we are told the original singular as orig
    orig = webster_original(page_src)
    if orig:
        ret = webster_lookup(orig)
        # overwrite
        ret['query'] = noun_lookup
        ret['base'] = orig
        return ret
    
    # h1 word is the word enclosed by html h1 tag
    h1_word = webster_find_h1_word(page_src)
    plurals = webster_find_plurals(page_src)

    ret = {}
    ret['query'] = noun_lookup
    if page_src.find('plural in form but singular or plural in construction') != -1:
        ret['wbs_2constrct'] = True
    # webster's base word is always h1 word
    # query can be redirected to base e.g. desks -> desk on webster
    ret['base'] = h1_word
    if plurals is None and ret['wbs_2constrct'] is True:
        ret['plural'] = [h1_word]
    elif plurals is None:
        ret['plural'] = []
    else:
        ret['plural'] = plurals
    return ret

# find feet is the plural of foot
def webster_original(txt):
    p1 = r'<span class="cxl">plural of</span> *<a href="[^"]*" class="cxt"><span class="text-uppercase">([^<]*)</span></a>'
    found = re.findall(p1, txt)
    if len(found) > 0:
        return found[0]
    else:
        return None

# at this point we know for sure we are reading a base_noun page
def webster_find_plurals(txt):
    rslt = webster_find_plural_a_or_b_also_c(txt)
    if rslt is not None:
        return rslt
    
    aorb = webster_find_plural_a_or_b(txt)
    if aorb is not None:
        plural_also = webster_find_plural_also(txt)
        if plural_also:
            final = aorb + plural_also
            final_set = set(final)
            return list(final_set) # we always return list
        else:
            return aorb
    
    aalsob = webster_find_plural_a_also_b(txt)
    if aalsob is not None:
        return aalsob  # forgot about other also, too much
    
    plu = webster_find_plural(txt)
    if plu is not None:
        return plu

    plu2 = webster_find_plural2(txt)
    if plu2 is not None:
        return plu2
    
    # webster cannot find its plural
    return None

# https://www.merriam-webster.com/dictionary/woman
def webster_find_plural(txt):
    p1 = r'plural&#32;</span><span class="if">([^<]*)</span>.*?'
    found = re.findall(p1, txt)
    if len(found) > 0:
        ret = []
        ret.append(found[0])
        return ret
    else:
        return None

# https://www.merriam-webster.com/dictionary/water
def webster_find_plural2(txt):
    p1 = '<span class="if">([^<]*)</span>(<span class="prt-a">| ).{0,2000}?<span class="spl plural badge mw-badge-gray-100 text-start text-wrap d-inline"> plural</span>'
    found = re.findall(p1, txt)

    new_found = []
    for item in found:
        if ' ' not in item[0]:
            new_found.append(item[0])

    set_found = set(new_found)
    lst_ret = list(set_found)
    return lst_ret

# https://www.merriam-webster.com/dictionary/foot
def webster_find_plural_a_also_b(txt):
    p1 = r'plural&#32;</span><span class="if">([^<]*)</span>.{0,2000}?'
    p2 = r'<span class="il "> also&#32;</span><span class="if">([^<]*)</span>'
    found = re.findall(p1+p2, txt)
    if len(found) > 0:
        return list(found[0])
    else:
        return None

# https://www.merriam-webster.com/dictionary/cactus
# should be very rare
def webster_find_plural_a_or_b_also_c(txt):
    # plural&#32;</span><span class="if">cacti</span><span class="prt-a">
    # or&#32;</span><span class="if">cactuses</span><span class="il ">
    # also&#32;</span><span class="if">cactus</span>

    # it becomes very slow if we have too much .*? limit its occurances
    # we used (.*?), but the performance was very bad, and there are some weird problem
    # we switched to (\w*), but cannot get some words with spaces, faux pas
    # we switched to [a-zA-Z0-9\- ], but for châteaus, it does not take â
    # so we eventually use [^<] to achieve the same
    p1 = r'plural&#32;</span><span class="if">([^<]*)</span>.{0,2000}?'
    p2 = r'<span class="il "> or&#32;</span><span class="if">([^<]*)</span>.{0,2000}?'
    p3 = r'<span class="il "> also&#32;</span><span class="if">([^<]*)</span>'
    # DOTALL must be used to let dot include newline
    # found = re.findall(pattern, txt, flags=re.DOTALL)
    # we remove line breaker before
    found = re.findall(p1+p2+p3, txt)
    if len(found) > 0:
        # found is list, but found[0] is tuple
        return list(found[0])
    else:
        return None

# https://www.merriam-webster.com/dictionary/octopus
# this return list or None
def webster_find_plural_a_or_b(txt):
    p1 = r'plural&#32;</span><span class="if">([^<]*)</span>.{0,2000}?'
    p2 = r'<span class="il "> or&#32;</span><span class="if">([^<]*)</span>'
    found = re.findall(p1+p2, txt)
    if len(found) > 0:
        # found is list, but found[0] is tuple
        return list(found[0])
    else:
        return None

# https://www.merriam-webster.com/dictionary/octopus
# this will return list or None
def webster_find_plural_also(txt):
    pattern = r'> plural also&#32;</span><span class="if">([^<]*)</span><span class="prt-a">'
    found = re.findall(pattern, txt)
    if len(found) > 0:
        # found is list
        return found
    else:
        return None

# -----------------------------------------------------------------------------
# word hippo look-up
def wordhippo_lookup(noun_lookup):
    logging.debug('sleep for one second between requests')
    time.sleep(1)
    if ' ' in noun_lookup:
        noun_lookup = noun_lookup.replace(' ', '_')
    url = 'https://www.wordhippo.com/what-is/the-plural-of/%s.html' % noun_lookup
    response = requests.get(url)
    if response.status_code != 200:
        logging.error(url + ' response: status_code[%d]' % response.status_code)
        return None
    page_src = response.text
    page_src = preprocess_text(page_src, keep_line_breaker = False)

    orig = wordhippo_original(page_src)
    if orig:
        ret = wordhippo_lookup(orig)
        # overwrite
        ret['query'] = noun_lookup
        ret['base'] = orig
        return ret

    plurals = wordhippo_find_plurals(page_src)
    if plurals is None:
        return None

    ret = {}
    ret['query'] = noun_lookup
    if page_src.find('<i>plural only</i>') != -1:
        ret['whp_plural_only'] = True
    # orig has been dealt with above
    ret['base'] = noun_lookup
    if len(plurals) > 0:
        ret['plural'] = plurals
    
    if page_src.find('can be countable or uncountable') != -1:
        ret['countable'] = WHP_NCT_EITHER
    elif page_src.find('is <i>uncountable</i>') != -1:
        ret['countable'] = WHP_NCT_UNCOUNTABLE
    else:
        ret['countable'] = WHP_NCT_COUNTABLE

    return ret

def wordhippo_original(txt):
    p1 = r'is the plural of <a href="/what-is/the-plural-of/[^"]*">([^<]*)</a>'
    found = re.findall(p1, txt)
    if len(found) > 0:
        return found[0]
    else:
        return None

def wordhippo_find_plurals(txt):
    if txt.find('No words found.') != -1:
        return None
    
    aorb = wordhippo_find_a_or_b(txt)
    if aorb is not None:
        return aorb
    
    aalsob = wordhippo_find_aalsob(txt)
    if aalsob is not None:
        return aalsob

    aalsob2 = wordhippo_find_aalsob2(txt)
    if aalsob2 is not None:
        return aalsob2

    a = wordhippo_find_a(txt)
    if a is not None:
        return a
    
    ao = wordhippo_find_also_only(txt)
    if ao is not None:
        return ao

    return None

# https://www.wordhippo.com/what-is/the-plural-of/octopus.html
def wordhippo_find_a_or_b(txt):
    p1 = r'plural form of \w* is <b><a[^>]*>([^<]*)</a></b> or <b>([^<]*)</b>'
    # this returns list of tuple
    found = re.findall(p1, txt)
    if len(found) > 0:
        return found[0]
    else:
        return None

# https://www.wordhippo.com/what-is/the-plural-of/foot.html
def wordhippo_find_a(txt):
    p1 = r'plural form of \w* is *<b><a[^>]*>([^<]*)</a></b>.'
    found = re.findall(p1, txt)
    if len(found) > 0:
        return found
    else:
        return None

# https://www.wordhippo.com/what-is/the-plural-of/water.html
def wordhippo_find_aalsob(txt):
    p1 = r'plural form will also be <b><a[^>]*>([^<]*)</a></b>.*?the plural form can also be <b><a[^>]*>([^<]*)</a></b>'
    found = re.findall(p1, txt)
    if len(found) > 0:
        return list(found[0])

    # no also
    p1 = r'plural form will be <b><a[^>]*>([^<]*)</a></b>.*?the plural form can also be <b><a[^>]*>([^<]*)</a></b>'
    found = re.findall(p1, txt)
    if len(found) > 0:
        return list(found[0])
    
    return None

# https://www.wordhippo.com/what-is/the-plural-of/deer.html
def wordhippo_find_aalsob2(txt):
    p1 = r'is also <b><a[^>]*>([^<]*)</a></b>'
    p2 = r'.*?the plural form can also be <b><a[^>]*>([^<]*)</a></b>'
    found = re.findall(p1+p2, txt)
    if len(found) > 0:
        return list(found[0])
    else:
        return None

def wordhippo_find_also_only(txt):
    p1 = 'is also <b><a href="/what-is/the-meaning-of-the-word/[^>]*">([^<]*)</a></b>.'
    found = re.findall(p1, txt)
    if len(found) == 1:
        return found
    elif len(found) > 1:
        return [found[0]]
    else:
        return None

def inflect_lookup(noun_lookup):
    engine = inflect.engine()
    plural = engine.plural(noun_lookup)
    ret = {}
    ret['query'] = noun_lookup
    ret['plural'] = [plural]
    ret['countable'] = WHP_NCT_UNKNOWN
    return ret

# we use a set of popular irregular nouns as the sanity test suite
# source of sanity test
# https://www.thoughtco.com/irregular-plural-nouns-in-english-1692634
# https://www.scientific-editing.info/blog/a-long-list-of-irregular-plural-nouns/
# only take very small part from scientific-editing
def sanity_test(website:str):
    df = pd.read_csv('sanity_test_irregular.csv', 
                      header=0)
    lst_sanity_rslt = []
    for word in df['singular']:
        if website == 'webster':
            lookedup = webster_lookup(word)
        elif website == 'wordhippo':
            lookedup = wordhippo_lookup(word)
        elif website == 'inflect':
            lookedup = inflect_lookup(word)
        else:
            return None

        dict_save = {}
        dict_save['query'] = word
        if lookedup is None: # cannot access the web, it returns None
            lst_sanity_rslt.append(dict_save)
            # we'll continue to try next
            continue

        sopo = lookedup.get('base', None)
        if sopo:
            dict_save['base'] = sopo

        lst_plural = lookedup.get('plural', [])
        if len(lst_plural) > 0:
            dict_save['plural_1'] = lst_plural[0]
        if len(lst_plural) > 1:
            dict_save['plural_2'] = lst_plural[1]
        if len(lst_plural) > 2:
            dict_save['plural_3'] = lst_plural[2]
        
        lst_sanity_rslt.append(dict_save)
        logging.info('finished gettting plurals for %s' % word)

    df_save = pd.DataFrame(lst_sanity_rslt)
    sanity_result = 'sanity_rslt_' + website + '.csv'
    try:
        os.remove(sanity_result)
    except OSError:
        pass
    df_save.to_csv( sanity_result, index = False)
    return

def sanity_test_all():
    sanity_test('webster')
    sanity_test('wordhippo')
    sanity_test('inflect')
    return

# The final user interface
# plc: plurals countable
# strict_level: dictionary - only return dictionary approved plurals
#               inclusive  - also return informal/unofficial ways that not approved 
#                              by dictionary but being used sometimes
#               forced     - get a plural even it's not a known noun                            
def pluc_lookup_plurals(noun:str, strict_level:str = 'dictionary'):
    webster_lookedup = webster_lookup(noun)
    wordhippo_lookedup = wordhippo_lookup(noun)

    if wordhippo_lookedup.get('countable', None):
        webster_lookedup['countable'] = wordhippo_lookedup['countable']

    sopo = None
    if webster_lookedup.get('base', None):
        sopo = webster_lookedup['base']
    elif wordhippo_lookedup.get('base', None):
        sopo = wordhippo_lookedup['base']
    
    wst_plu = webster_lookedup.get('plural', [])
    whp_plu = wordhippo_lookedup.get('plural', [])

    if strict_level == 'dictionary':
        # we return webster approved if we can, then turn into
        # wordhippo later
        if len(wst_plu) > 0:
            return webster_lookedup
        else:
            # wordhippo_lookedup might just contain empty plural
            return wordhippo_lookedup
    else:
        # we will combine what we have to have possible as many plural as possible
        wst_plu = webster_lookedup.get('plural', [])
        whp_plu = wordhippo_lookedup.get('plural', [])

        # get the max possible set
        max_plu = [*set(wst_plu + whp_plu)]
        if len(max_plu) > 0:
            ret = {}
            ret['query'] = noun
            ret['base'] = sopo
            ret['plural'] = max_plu
            return ret
        
        # at this point, if we do not find a plural, we need give up if level is inclusive
        if strict_level == 'inclusive':
            ret = {}
            ret['query'] = noun
            ret['plural'] = []
            # we just put what we have and return an empty plural list
            return ret
        
        # this is the last resort for strict_level is forced
        return inflect_lookup()

def main():
    sanity_test_all()
    rslt = pluc_lookup_plurals('woman', strict_level='dictionary')
    print(rslt)
    rslt = pluc_lookup_plurals('men', strict_level='dictionary')
    print(rslt)
    rslt = pluc_lookup_plurals('desk', strict_level='dictionary')
    print(rslt)
    rslt = pluc_lookup_plurals('soleness', strict_level='dictionary')
    print(rslt)
    rslt = pluc_lookup_plurals('my', strict_level='forced')
    print(rslt)

if __name__ == "__main__":
    main()