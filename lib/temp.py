import os
import requests
import urllib
import json
import openai
import rollbar
import trafilatura
import pandas as pd
import numpy as np
import xml.etree.ElementTree as ET
import tiktoken
import random
import re
from urllib.parse import urlparse, urlunparse
import tldextract
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
# import spacy
# import unicodedata
from geopy.geocoders import Nominatim
from geotext import GeoText

import os.path
import site
site.addsitedir(os.path.join(os.path.dirname(__file__), '..'))
from lib.markupper import Markupper

from dotenv import load_dotenv
load_dotenv()

url = 'https://www.chasingthedonkey.com/best-things-to-do-in-croatia/'

# a = Markupper()
# b = a.create_page_markup(url)
# print(b)

sentence= 'Explore the Old Town, walk the city walls, and visit Fort Lovrijenac and the Rector’s Palace'
text = 'Dubrovnik:Known as the “Pearl of the Adriatic,” Dubrovnik is a stunning city with ancient walls, marble streets, and historic buildings. Explore the Old Town, walk the city walls, and visit Fort Lovrijenac and the Rector’s Palace.Explore the Old Town,walk the city walls, and visit Fort Lovrijenacand the Rector’s Palace.'

print(sentence[0:15])