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
    """
    This function removes all non-space characters from a string and then joins
    the remaining space-separated words back into a single string.

    Args:
        mystring (str): In the function `str_normalize_whitespace`, `mystring` is
            the input string to be normalized.

    Returns:
        str: The output returned by the `str_normalize_whitespace` function is a
        string that is the result of joining all the words of the input string
        using spaces as separators.

    """
    return ' '.join(mystring.split())

def str_merge_whitespaces(mystring):
    """
    This function takes a string `mystring` and removes leading and trailing white
    spaces by replacing sequences of two or more whitespace characters with a
    single space.

    Args:
        mystring (str): The `mystring` input parameter is the string that needs
            to be merged and freed of extra whitespace.

    Returns:
        str: The output returned by this function is the original string with all
        adjacent whitespace characters (spaces and tabs) reduced to a single space.

    """
    mystring = mystring.strip()  # the while loop will leave a trailing space,
                                 # so the trailing whitespace must be dealt with
                                 # before or after the while loop
    while '  ' in mystring:
        mystring = mystring.replace('  ', ' ')
    return mystring

def preprocess_text(txt, keep_line_breaker = True):
    # we can also replace, but unicode lib is a much better way
    # x['text'] = x['text']replace(u'\xa0', u' ')
    """
    This function preprocesses text by performing the following operations:
    1/ Normalizing the text to NFKD (NF Kalman Decomposition) using `unicodedata`.
    2/ Removing whitespace characters other than ASCII spaces using `str_merge_whitespaces`.
    3/ If `keep_line_breaker` is `True`, the function returns the normalized text
    with line breaks preserved; otherwise it removes line breaks.

    Args:
        txt (str): The `txt` input parameter is the text that needs to be preprocessed.
        keep_line_breaker (bool): The `keep_line_breaker` input parameter specifies
            whether to retain line breaks (newlines) present inside the text.

    Returns:
        str: The output returned by this function is a string with normalized whitespaces.

    """
    txt = unicodedata.normalize('NFKD', txt)
    if keep_line_breaker:
        return str_merge_whitespaces(txt)
    else:
        return str_normalize_whitespace(txt)

# -----------------------------------------------------------------------------
# webster look-up
def webster_find_h1_word(text):
    # pattern: <h1 class="hword">foot</h1>
    """
    This function takes a string of text as input and extracts the first occurrence
    of an H1 word (a heading with the class "hword") from the text.

    Args:
        text (str): The `text` input parameter is the string of HTML content that
            is being analyzed to find an H1 word.

    Returns:
        str: The output returned by this function is `None`.

    """
    h1_word = re.findall(r'<h1 class="hword">(.*?)</h1>', text)

    if len(h1_word) > 0:
        return h1_word[0]
    else:
        return None

# webster does not recognize this word or it's mispelled
def webster_is_mispelled(web_src):
    # <h1 class="mispelled-word">&ldquo;duckss&rdquo;</h1>
    """
    This function takes a string as input (web_src) and returns true if it contains
    an h1 tag with a class of "mispelled-word" otherwise it returns false.

    Args:
        web_src (str): The `web_src` input parameter is passed as an argument to
            the function and serves as a string of HTML code that is checked for
            misspellings using the provided regular expression.

    Returns:
        str: The function takes a string `web_src` as input and checks if it
        contains the word "<h1 class="mispelled-word">" anywhere inside it.

    """
    if web_src.find('<h1 class="mispelled-word">') != -1:
        return True
    else:
        return False

def webster_lookup(noun_lookup):
    """
    This function takes a noun string as input and uses the Merriam-Webster API
    to retrieve information about it.

    Args:
        noun_lookup (str): The `noun_lookup` parameter is the word or phrase that
            the user looks up for its definition using the Merriam-Webster online
            dictionary.

    Returns:
        dict: The output returned by this function is a dictionary with the following
        keys:
        
        	- `query`: The original noun lookup term.
        	- `base`: The base word found on Webster's page (usually the h1 word).
        	- `plural`: A list of plural forms found on Webster's page.
        	- `wbs_2constrct`: A boolean indicating if the query is a constructive
        singular form (e.g., "desks" is a constructive singular form of "desk").
        
        The function returns this dictionary regardless of whether the lookup term
        has an plural forms or not.

    """
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
    """
    This function extracts the plural form of a word from a given text using regular
    expressions. It searches for occurrences of "<span class="cxl">plural of</span>"
    followed by an <a> tag with a link to another page and an arbitrary number of
    characters inside a span tag.

    Args:
        txt (str): The `txt` input parameter is the string that should be searched
            for plural forms using regular expressions.

    Returns:
        list: The output returned by this function is `None`.

    """
    p1 = r'<span class="cxl">plural of</span> *<a href="[^"]*" class="cxt"><span class="text-uppercase">([^<]*)</span></a>'
    found = re.findall(p1, txt)
    if len(found) > 0:
        return found[0]
    else:
        return None

# at this point we know for sure we are reading a base_noun page
def webster_find_plurals(txt):
    """
    This function takes a string `txt` and returns its plural form according to
    Webster's rules. If no plural form is found using webster's rules the function
    returns none.

    Args:
        txt (str): The `txt` input parameter is passed as an argument to various
            other functions within the `webster_find_plurals` function. These
            functions are responsible for finding the plural form of a word or
            phrase based on different rules and conventions. The output of these
            functions is then used to construct the final plural form of the input
            text. In essence.

    Returns:
        list: The output returned by this function is a list of strings. If any
        of the "a", "b", or "also" plural forms are found (in that order), a list
        of those words will be returned.

    """
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
    """
    This function takes a string `txt` as input and returns an array of strings
    representing the plural forms found within `txt`. It uses regular expressions
    to identify groups of words followed by a span tag with a class of "if",
    extracts the text inside those spans and returns it as an array of plural forms.

    Args:
        txt (str): The `txt` input parameter is the text that needs to be checked
            for plurals.

    Returns:
        list: The output returned by this function is a list containing the first
        occurrence of the word with its plural form.

    """
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
    """
    This function takes a string "txt" and extracts all singular nouns (i.e., words
    without spaces) that are not preceded by a space and returns them as a list.

    Args:
        txt (str): The `txt` input parameter is the string that will be searched
            for plural forms using regular expressions.

    Returns:
        list: The output returned by this function is a list of all words found
        with the pattern '<span class="if">([^<]*)</span>(<span class="prt-a">| ).{0.
        .

    """
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
    """
    This function searches for plural forms of words within a given text using
    regular expressions. It first searches for <span class="if"> patterns and then
    checks if the text between these patterns contains any plural forms by checking
    if it matches the regular expression r'[^<]*'. If there are any matches it
    returns a list of all the matches.

    Args:
        txt (str): The `txt` input parameter is the text that the function will
            search for plural forms of words.

    Returns:
        list: The output returned by this function is `None`.

    """
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
    """
    This function takes a string "txt" as input and finds all occurrences of words
    that can be made plural using the rules of English grammar.

    Args:
        txt (str): The `txt` input parameter is the string that the function
            processes to find plural forms of words.

    Returns:
        list: The output returned by the `webster_find_plural_a_or_b_also_c`
        function is a list of words that are found to be plural forms of the input
        text.

    """
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
    """
    This function searches for plural forms of words within a text and returns the
    first match. It uses regular expressions to identify plural forms denoted by
    "<span class="if">" tags containing one or more letters that are not angles
    (i.e., any character except <). The function first finds all matches using two
    regular expressions: the first for single words (such as "dog") and the second
    for phrases ending with "or" (such as "dogs or cats").

    Args:
        txt (str): The `txt` input parameter is the text to search for plural forms
            of words.

    Returns:
        list: The output returned by the `webster_find_plural_a_or_b` function is
        `None`.

    """
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
    """
    This function uses regular expressions to find all occurrences of the phrase
    "plural also" and any following text that is enclosed within a span tag with
    a specific class name (e.g., "prt-a") within a given string (represented by
    the variable "txt").

    Args:
        txt (str): In the `webster_find_plural_also()` function provided:
            
            The `txt` input parameter serves as the text content being analyzed
            to identify instances of "plural also" phrases and retrieve any
            corresponding singular words.

    Returns:
        list: The output returned by the function is a list of all plural forms
        foundin the input text. If no plural forms are found.

    """
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
    """
    This function takes a string as input (a noun to look up) and uses the WordHippo
    API to retrieve information about the plural form of that noun.

    Args:
        noun_lookup (str): The `noun_lookup` input parameter is used to pass the
            word or phrase that we want to look up the plural form of.

    Returns:
        dict: The function "wordhippo_lookup" returns a dictionary containing the
        following information:
        
        	- 'query': The original noun lookup string.
        	- 'base': The base form of the word (the same as the input parameter).
        	- 'plural': A list of possible plural forms of the word (if found).
        	- 'whp_plural_only': A flag indicating if the only available plural form
        is <i>plural only</i>.
        	- 'countable': A flag indicating if the word can be countable or uncountable
        (one of WHP_NCT_COUNTABLE/WHP_NCT_UNCOUNTABLE/WHP_NCT_EITHER).

    """
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
    """
    This function takes a string `txt` and extracts the plural form of the first
    word that is a link to a Wikipedia page about the plural form of a word.

    Args:
        txt (str): The `txt` input parameter is the string that contains the text
            to be analyzed for plural forms.

    Returns:
        list: The output returned by this function is `None`.

    """
    p1 = r'is the plural of <a href="/what-is/the-plural-of/[^"]*">([^<]*)</a>'
    found = re.findall(p1, txt)
    if len(found) > 0:
        return found[0]
    else:
        return None

def wordhippo_find_plurals(txt):
    """
    This function checks if any words can be found using a list of predicates
    (`wordhippo_find_a`, `wordhippo_find_b`, `wordhippo_find_also_only`, and
    `wordhippo_find_aalsob`) and returns the first one that matches.

    Args:
        txt (str): The `txt` input parameter is the string that needs to be processed
            to find plurals.

    Returns:
        str: The output returned by this function is "None".

    """
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
    """
    The function `wordhippo_find_a_or_b(txt)` finds all occurrences of a word
    followed by either an <a> tag or a </a> tag within a <b> tag or</b> tag and
    returns the first match as a tuple or None if no matches are found.

    Args:
        txt (str): The `txt` input parameter is the text that should be searched
            for plural forms of words.

    Returns:
        list: Based on the regular expression provided and the sample text "This
        is a sample text with some plural forms", the output returned by the
        `wordhippo_find_a_or_b` function is `('plural form of \w* is <b>([^<]*)</b>)
        or <b>([^<]*)</b>]`.

    """
    p1 = r'plural form of \w* is <b><a[^>]*>([^<]*)</a></b> or <b>([^<]*)</b>'
    # this returns list of tuple
    found = re.findall(p1, txt)
    if len(found) > 0:
        return found[0]
    else:
        return None

# https://www.wordhippo.com/what-is/the-plural-of/foot.html
def wordhippo_find_a(txt):
    """
    This function finds all instances of words with a plural form (i.e., words
    that end with an 's' or an 'es'') within a given text string using regular
    expressions and returns a list of those word matches.

    Args:
        txt (str): The `txt` parameter is the text string that we want to search
            for plural forms of words.

    Returns:
        list: The function `wordhippo_find_a` uses a regular expression to search
        for plural forms of words on the input text `txt`. The output returned by
        this function is a list of plural form of words found on the input text
        or an empty list if no such forms were found.

    """
    p1 = r'plural form of \w* is *<b><a[^>]*>([^<]*)</a></b>.'
    found = re.findall(p1, txt)
    if len(found) > 0:
        return found
    else:
        return None

# https://www.wordhippo.com/what-is/the-plural-of/water.html
def wordhippo_find_aalsob(txt):
    """
    This function takes a string `txt` as input and searches for instances of words
    that have both a plural form and also a definition or description. It uses
    regular expressions to match patterns that indicate the word has multiple
    forms. If such a word is found. The function returns the word and its definition(s).

    Args:
        txt (str): The `txt` input parameter is the text that should be searched
            for plural forms of words.

    Returns:
        list: The output returned by this function is `None`.

    """
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
    """
    This function finds all occurrences of the phrase "is also" and "the plural
    form can also be" with their corresponding brackets and URLs (if present)
    within a given text.

    Args:
        txt (str): The `txt` input parameter is the string that we want to search
            for words with both forms (singular and plural) using regular expressions.

    Returns:
        list: The output returned by this function is "is" because the regular
        expression pattern search finds a match for "is" as the first word followed
        by a nested link tag ("<b><a[^>]*>([^<]*)</a></b>") and then another nested
        link tag ("<b><a[^>]*>([^<]*)</a></b>").

    """
    p1 = r'is also <b><a[^>]*>([^<]*)</a></b>'
    p2 = r'.*?the plural form can also be <b><a[^>]*>([^<]*)</a></b>'
    found = re.findall(p1+p2, txt)
    if len(found) > 0:
        return list(found[0])
    else:
        return None

def wordhippo_find_also_only(txt):
    """
    This function finds all occurrences of words that are followed by the phrase
    "is also <b><a href=". It returns a list of these words if there is more than
    one match or a single word if there is only one match.

    Args:
        txt (str): The `txt` input parameter is the text to search for words that
            are also defined as hyperlinks.

    Returns:
        list: The function `wordhippo_find_also_only` takes a string `txt` as input
        and returns a list of strings or `None`.
        
        The function first finds all occurrences of the pattern `<b><a
        href="/what-is/the-meaning-of-the-word/[^>]*">([^<]*)</a></b>` using regular
        expressions. If there is only one match found then the function returns a
        list containing that match.
        If there are multiple matches then it return only the first match found .

    """
    p1 = 'is also <b><a href="/what-is/the-meaning-of-the-word/[^>]*">([^<]*)</a></b>.'
    found = re.findall(p1, txt)
    if len(found) == 1:
        return found
    elif len(found) > 1:
        return [found[0]]
    else:
        return None

def inflect_lookup(noun_lookup):
    """
    This function takes a noun look-up string as input and returns a dictionary
    with the following contents:
    	- "query": The original noun look-up string.
    	- "plural": The plural form of the noun determined by the Inflect engine.
    	- "countable": A value indicating whether the noun is countable (known or unknown).

    Args:
        noun_lookup (str): The `noun_lookup` parameter is a string that contains
            the word or phrase for which the plural form should be retrieved.

    Returns:
        dict: The function `inflect_lookup` returns a dictionary with the following
        keys and values:
        
        	- `query': The original noun lookupt (string)
        	- `plural': The plural form of the noun lookupt (list of strings)
        	- `countable': The countability status of the noun (integer value: 1 for
        countable nouns and 0 for uncountable nouns)
        
        So the output returned by this function is a dictionary with three key-value
        pairs.

    """
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
    """
    This function performs a sanity check on a given website by comparing it to a
    list of known words and their plural forms.

    Args:
        website (str): The `website` input parameter specifies which online resource
            to use for looking up the word's plural form.

    Returns:
        : The function does not return anything.

    """
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
    """
    This function tests three different dictionaries (or similar modules) for
    correctness by running a `sanity_test` function on each one.

    """
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
    """
    This function looks up plurals for a given noun using two different dictionaries
    (Webster and WordHippo) and combines their results to provide the most
    comprehensive list of possible plurals.

    Args:
        noun (str): The `noun` input parameter specifies the word for which to
            look up the plural form.
        strict_level ('dictionary'): The `strict_level` input parameter determines
            the level of strictness with which to return a plural form.

    Returns:
        dict: The output returned by this function is a dictionary containing the
        following keys:
        
        	- 'query': The original input noun
        	- 'base': The base form of the noun (either webster_lookedup['base'] or
        wordhippo_lookedup['base'])
        	- 'plural': A list of possible plurals for the noun (generated by combining
        webster_lookedup['plural'] and wordhippo_lookedup['plural'])
        
        The function returns an empty list ('[]) if it cannot find any plural forms
        for the noun.

    """
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
    '''for testing'''
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