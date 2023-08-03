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

from dotenv import load_dotenv
load_dotenv()

class Markupper:
    def __init__(self):
        openai.api_key = os.getenv("OPEN_AI_API_KEY")
        self.model = "gpt-3.5-turbo-16k"
        self.max_tokens=7000
        self.result = []
        self.messages = [
            ##todo - bad and good POI examples
            {"role": "system", "content": "You are travel-blooger assistant that needs to find all POIs and geo objects in the text. If an sentence has any of them, then return JSON array with sentence and array of objects you found"},
            {"role": "user", "content": "Find all POIs and geo objects here: Explore the Old Town, walk the city walls, and visit Fort Lovrijenac and the Rector’s Palace. Aslo don't forget to take an umbrealla. It will take about 3 hours to see everything."},
            {"role": "assistant", "content": "[{\"sentence\":\"Explore the Old Town, walk the city walls, and visit Fort Lovrijenac and the Rector’s Palace\", \"POIs\": \"[\"Old Town\", \"Fort Lovrijenac\", \"Rector’s Palace\"]\"}]"} 
        ]

    def create_page_markup(self,url):
        self.result = []
        self.url = url 
        self.get_page_text()
        self.chunk_text()
        self.chat_gpt_markup()
        self.create_poi_pd()
        self.check_if_poi_is_link()
        return self.df
    
    def check_if_poi_is_link(self):
        soup = BeautifulSoup(self.html, 'html.parser')
        links = soup.find_all('a')

        self.df['has_link'] = False
        self.df['link'] = "new"

        for index, row in self.df.iterrows():
            poi = row['POI']
            sentence = row['sentence']
            for link in links:
                if poi in link.text:
                    parent_text = link.parent.get_text(strip=True)
                    if sentence[0:15] in parent_text:
                        href = link.get('href')                        
                        self.df.at[index, 'has_link'] = True
                        self.df.at[index, 'link'] = href

    
    def create_poi_pd(self):
        df = pd.DataFrame(columns=["url", "sentence","POI"])

        for sentense in self.gtp_markup:
            for poi in sentense["POIs"]:
                if len(poi) < 2:
                    print('AAAA')
                row = []
                row.append(self.url)
                row.append(sentense["sentence"])
                row.append(poi)
                print(row)
                df.loc[len(df.index)] = row

        
        self.df = df
        
    
    def chat_gpt_markup(self):
        self.gtp_markup = []

        for chunk in self.chunks:
            input = []
            input = self.messages + [{"role": "user", "content": "Awesome, now do it for:{0}".format(chunk)}]
            
            max_attempts = 3
            attempts = 0
            
            while attempts < max_attempts:
                completion = openai.ChatCompletion.create(
                    model=self.model,
                    messages=input
                )
                
                a = completion['choices'][0]['message']['content']  # type: ignore
                try:
                    a = json.loads(a)
                    for b in a:
                        self.gtp_markup.append(b)
                    break
                except:
                    print('FOK')
                    attempts +=1

    def chunk_text(self):
        encoding = tiktoken.get_encoding("cl100k_base")
        encoding = tiktoken.encoding_for_model(self.model)

        # Tokenize the text
        tokens = encoding.encode(self.blob)
        
        # Divide the tokens into 7000-token chunks
        self.chunks = [tokens[i:i + self.max_tokens] for i in range(0, len(tokens), self.max_tokens)]

        # Decode the tokens back into text
        self.chunks = [encoding.decode(chunk) for chunk in self.chunks]
    
    def get_page_text(self):
        try:
            ua = UserAgent()
            headers = {'User-Agent': ua.random}
            result = ''
            response = requests.get(self.url, headers=headers)
            if response.status_code == 200:
                self.html = response.text
                useful_text = trafilatura.extract(response.text, include_links=False, include_comments=False, output_format='xml') 
                useful_text = ET.fromstring(useful_text)  # type: ignore
                blob = ""
                for element in useful_text.iter():
                    if element.tag in ['p', 'item']:
                        if element.text and element.text.strip():
                            blob += element.text.strip() + ' '
                        for child in element:
                            blob += ET.tostring(child, encoding='unicode').strip() + ' '
                self.blob = blob            
        except:
            print('пизда рулю')