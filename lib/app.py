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

dataset = ['https://www.chasingthedonkey.com/best-things-to-do-in-croatia/']

result = pd.DataFrame()

for url in dataset:
    markupper = Markupper()
    result = pd.concat([result, markupper.create_page_markup(url)], ignore_index=True)

print(result)
result.to_csv('result.csv', index=False)