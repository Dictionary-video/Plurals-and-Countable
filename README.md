Plurals-and-Countable
==============
A python library that returns plurals of a noun and indicates whether the noun is countable or not.

# Why do we build another plural library for nouns?
Most of the existing libraries pluralize a noun and return one possible plural form. As we know for some irregular nouns, there are multiple plural forms available. Sometimes, whether a plural form is appropriate is also debatable and some people prefer one over another. 

Plurals-and-Countable does not use rules to pluralize it or use a huge dataset to learn. It simply looks it up in a dictionary. So unlike other plural libraries, Plurals-and-Countable can
1. return **multiple plural forms** if a word has them;
2. return **dictionary-approved** plurals or inclusively some generally used plural forms but not in dictionaries yet.
3. indicate whether a noun is countable or not, or either way.

# How to use it?
```
import plurals_countable as pluc
# strict_level: dictionary - only return dictionary approved plurals
#               inclusive  - also return informal/unofficial ways that not approved 
#                              by dictionary but being used sometimes
#               forced     - get a plural even it's not a known noun
rslt = pluc.pluc_lookup_plurals('octopus', strict_level='dictionary')
print(rslt)
```

# Understand the return value
The look-up of octopus returns
```
{
    'query': 'octopus', 
    'base': 'octopus', 
    'plural': ['octopuses', 'octopi', 'octopodes'], 
    'countable': 'countable'
}
```

It returns three possible plurals. Singular for octopus is octopus, so **base** is octopus. We do not name **base** as singular, because some plural-only words do not even have singular.

The look-up of men returns
```
{
    'query': 'men', 
    'base': 'man', 
    'plural': ['men'], 
    'countable': 'countable'
}
```
The base is **man**, and it's different from the query.

The look-up of air returns
```
{
    'query': 'air', 
    'base': 'air', 
    'plural': ['air, airs'], 
    'countable': 'either'
}
```
Believe it or not, air can be countable when it refers to an artificial way of acting, e.g. *put on airs*. So the plural list contains both air and airs. Countable is either, which means it can be countable or uncountable depending on word meanings.

# When strict_level is forced
Plurals-and-Countable does not verify the passed parameter is a noun. When it is not a noun, a dictionary look-up is very likely to return nothing. But you can always use strict_level = forced to force an output. The library uses *inflect* to return a value. We do not know what is the proper base or whether it's countable or not when *inflect* is triggered.
If you call the library by passing on *enjoy*, which is not a noun, with strict_level is forced. This is what you will get.
```
    'query': 'enjoy', 
    'plural': ['enjoys'], 
    'countable': 'unknown'
```
Our goal is that our library covers nearly all known nouns so that you'll never need to use forced.

# Sanity test
Along with the source code, a sanity test suite is provided for most irregular nouns. You may run the sanity test by
```
sanity_test_all()
```
It will generate three sanity test results.

# Cache is recommended
It takes time to look up a dictionary every time, and the library also limits the interval between look-ups to not overwhelm the dictionary. 

It is recommended that you implement some local cache mechanism or put the results in a database for future look-up.

# Alternative REST API call
For better performance, [Dictionary.video](https://dictionary.video) provides a REST API you can call. You'll need to contact us at admin@dictionary.video to get an API key.
```
curl https://dictionary.video/api/noun/plurals/octopus?key=REPLACE_WITH_YOUR_KEY
```
Like Plurals-and-Countable, the API call returns a dictionary containing query, base and a list of plurals.

There are some corner cases when automatic look-ups fail. REST API might have manual fixes of those corner cases by our editors.

# LICENSE
Plurals-and-Countable by [Dictionary.video](https://dictionary.video) is licensed under a Creative Commons Attribution-ShareAlike 4.0 International License. Please follow the license requirement to acknowledge [Dictionary.video-about](https://dictionary.video/about.html) in any proper manner.
