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
        self.blob = ""
        self.html = ""
        self.markup_default_messages = [
            ##todo - bad and good POI examples
            ##todo - define POI
            {"role": "system", "content": "You are travel-blooger assistant that needs to find all POIs and geo objects in the text. If an sentence has any of them, then return JSON array with sentence and array of objects you found"},
            {"role": "user", "content": "Find all POIs and geo objects here: Explore the Old Town, walk the city walls, and visit Fort Lovrijenac and the Rector’s Palace. Aslo don't forget to take an umbrella. It will take about 3 hours to see everything."},
            {"role": "assistant", "content": "[{\"sentence\":\"Explore the Old Town, walk the city walls, and visit Fort Lovrijenac and the Rector’s Palace\", \"POIs\": [\"Old Town\", \"Fort Lovrijenac\", \"Rector’s Palace\"]}]"},
            {"role": "user", "content": "Also POI can be a sentence itself. Like this: \"sentence\":\"California Tower.\""},
            {"role": "assistant", "content": "[{\"sentence\":\"California Tower.\", \"POIs\": [\"California Tower\"]}]"} 
        ]
        self.verticals_default_messages = [
            ##todo - bad and good examples
            {"role": "system", "content": "You are travel-blooger assistant that needs to find out witch topic matches with a POI from a sentence. Reply in JSON format like {\"Topics\":[\"Topic1\",\"Topic2\"]}"},
            {"role": "system", "content": "List of topics is Flights, Hotels, Tours and Activities, Car Rental, SIM-cards, Insurance, Bike rental, Food and Dining, Bus and train tickets, Sanatoriums, Transfers, Cruises, Boat Rental, Nightlife, Travel Gear"},
            {"role": "user", "content": "\"sentence\":\"Explore the Old Town, walk the city walls, and visit Fort Lovrijenac and the Rector’s Palace.\",\"POI:\":\"Old Town\""},
            {"role": "assistant", "content": "{\"Topics\":[\"Tours and Activities\"]}"} 
        ]

    def create_page_markup(self,url):
        #main flow to reach the result
        self.result = []
        self.url = url 
        #get page html and useful text from url
        self.get_page_text()
        #divide text into chunks due to OpenAI API tokens limit
        self.chunk_text()
        #get page markup by ChatGTP
        self.chat_gpt_markup()
        #create dataframe with POIs
        self.create_poi_pd()
        #check if POI has a link
        self.check_if_poi_is_link()
        #get POI vertical from sentence context
        self.get_poi_topic()
        return self.df
    
    def get_poi_topic(self):

        for index, row in self.df.iterrows():
            poi = row['POI']
            sentence = row['sentence']

            input = []
            input = self.verticals_default_messages + [{"role": "user", "content": "Awesome, now do it for:\"sentence\":\"{0}\",\"POI\":\"{1}\",".format(sentence,poi)}]

            completion = openai.ChatCompletion.create(
                        model=self.model,
                        messages=input
                    )
                    
            temp = completion['choices'][0]['message']['content']  # type: ignore
            try:
                temp = json.loads(temp)
                self.df.at[index, 'topics'] = ', '.join(temp['Topics'])
            except:
                print('Couldn\'t get topic for:',sentence)
    
    def check_if_poi_is_link(self):
        soup = BeautifulSoup(self.html, 'html.parser')
        links = soup.find_all('a')

        self.df['has_link'] = False
        self.df['link'] = "new"
        self.df['placement'] = None

        for index, row in self.df.iterrows():
            poi = row['POI']
            sentence = row['sentence']
            no_link = True
            for link in links:
                if poi in link.text:
                    parent_text = link.parent.get_text(strip=True)
                    if sentence[0:15] in parent_text:
                        no_link = False
                        href = link.get('href')                        
                        self.df.at[index, 'has_link'] = True
                        self.df.at[index, 'link'] = href
                        self.df.at[index, 'placement'] = link.text
                        if 'tp.media' in href or 'tp.st' in href:
                            self.df.at[index, 'link_type'] = 'partner_tp'
                        elif urlparse(href).netloc == urlparse(self.url).netloc:
                            self.df.at[index, 'link_type'] = 'internal'
                        else:
                            self.df.at[index, 'link_type'] = 'other'
            if no_link:
                self.df.at[index, 'has_link'] = False
                self.df.at[index, 'link'] = None
                self.df.at[index, 'link_type'] = 'new'   
                self.df.at[index, 'placement'] = poi
    
    def create_poi_pd(self):
        df = pd.DataFrame(columns=["url", "sentence","POI"])

        for sentense in self.gtp_markup:
            if "POIs" in sentense:
                for poi in sentense["POIs"]:
                    if len(poi) > 2:
                        row = []
                        row.append(self.url)
                        row.append(sentense["sentence"])
                        row.append(poi)
                        df.loc[len(df.index)] = row  # type: ignore
            else:
                print("Now POIs in sentense",sentense,self.url)

        self.df = df
        
    
    def chat_gpt_markup(self):
        self.gtp_markup = []

        for chunk in self.chunks:
            input = []
            input = self.markup_default_messages + [{"role": "user", "content": "Awesome, now do it for:{0}".format(chunk)}]
            
            max_attempts = 5
            attempts = 0
            
            while attempts < max_attempts:
                completion = openai.ChatCompletion.create(
                    model=self.model,
                    messages=input
                )
                
                a = completion['choices'][0]['message']['content']  # type: ignore
                err = completion['choices'][0]['finish_reason']  # type: ignore
                try:
                    a = json.loads(a)
                    for b in a:
                        self.gtp_markup.append(b)
                    break
                except Exception as e:
                    print('Couldn\'t create markup for:',self.url,err, str(e))
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
            print("Couldn't get page content for ",self.url)