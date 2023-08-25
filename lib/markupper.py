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
    def __init__(self,url,html):
        openai.api_key = os.getenv("OPEN_AI_API_KEY")
        self._model = "gpt-3.5-turbo-16k"
        self._max_tokens=7000
        self._max_regenerations = 3
        self.result = []
        self.trafilatura_blob = ""
        self.html = ""
        self.useful_text = ""
        self.markup_default_messages = [
            ##todo - bad and good POI examples
            ##todo - define POI
            {"role": "system", "content": "You are travel-blooger assistant that needs to find all POI in the text. If an sentence has any of them, then return JSON array with sentence and array of objects you found. POI is some location, object, museumm seesight etc."},
            {"role": "user", "content": "Find all POIs and geo objects here: Explore the Old Town, walk the city walls, and visit Fort Lovrijenac and the Rector’s Palace. Aslo don't forget to take an umbrella. It will take about 3 hours to see everything."},
            {"role": "assistant", "content": "[{\"sentence\":\"Explore the Old Town, walk the city walls, and visit Fort Lovrijenac and the Rector’s Palace\", \"POIs\": [\"Old Town\", \"Fort Lovrijenac\", \"Rector’s Palace\"]}]"},
            {"role": "user", "content": "Also POI can be a sentence itself. Like this: \"sentence\":\"California Tower.\""},
            {"role": "assistant", "content": "[{\"sentence\":\"California Tower.\", \"POIs\": [\"California Tower\"]}]"},
            {"role": "user", "content": "But if POI isn't separated with dots writhe the whole sentence. Like this: \"sentence\":\"One of them, California Tower.\""},
            {"role": "assistant", "content": "[{\"sentence\":\"One of them, California Tower.\", \"POIs\": [\"California Tower\"]}]"},
            {"role": "user", "content": "And POI can't be something that's not a place. Like this: \"sentence\":\"Zara — Located the world over but with a heavy presence in Europe.\""}, 
            {"role": "assistant", "content": "[{\"sentence\":\"None\", \"POIs\": []}]"},
            {"role": "user", "content": "Another exmaple with no POI: \"sentence\":\"The Adventure Pass Classic allows you to enjoy six attractions\""}, 
            {"role": "assistant", "content": "[{\"sentence\":\"None\", \"POIs\": []}]"},
        ]
        self.verticals_default_messages = [
            ##todo - bad and good examples
            {"role": "system", "content": "You are travel-blooger assistant that needs to find out witch topic matches with a POI from a sentence. Reply in JSON format like {\"Topics\":[\"Topic1\",\"Topic2\"]}"},
            {"role": "system", "content": "List of topics is Flights, Hotels, Tours and Activities, Car Rental, Bike rental, Food and Dining, Bus and train tickets, Sanatoriums, Transfers, Cruises, Boat Rental, Nightlife. Don't use any other topics. If none of these is applicable just skip it."},
            {"role": "user", "content": "Good example: \"sentence\":\"Explore the Old Town, walk the city walls, and visit Fort Lovrijenac and the Rector’s Palace.\",\"POI:\":\"Old Town\""},
            {"role": "assistant", "content": "{\"Topics\":[\"Tours and Activities\"]}"},
            {"role": "user", "content": "Bas example: \"sentence\":\"Ellos – Founded in 1947, they are Sweden’s leading online department store, with collections that reflect Swedish lifestyle & design aesthetics in sizes 10+.\", and \"POI:\":\"Ellos\".Reply shouldn't be like \"{\"Topics\":[\"Fashion\"]}\" "},
            {"role": "assistant", "content": "{\"Topics\":[]}"} 
        ]
        self._get_meta_location_data_prompt = [
            {"role": "system", "content": "You are travel-blooger assistant that needs to make summary about blog page"},
            {"role": "user", "content": "You need to find out what cities or countries relates or are mentioned in the next text. Then for selected city answer if renting a car make sense when visiting this location (use true or false) and what is nearest airport's IATA"},
            {"role": "assistant", "content": "Ok"},
            {"role": "user", "content": "If only country is mentioned set city, cars and airporst as null. If city is mentioned specify country where the city is located"},
            {"role": "assistant", "content": "Got it"},
            {"role": "user", "content": "Use oficial and full names of cities and countries. \"St Lucia\" is bad reply, \"Saint Lucia\" is the correct one."},
            {"role": "assistant", "content": "Right"},
            {"role": "user", "content": "Reply strictly in JSON format without any additional text. For example for Venice, Italy it should be {\"city\":\"Venice\",\"country\":\"Italy\",\"car rental\":false,\"IATA\":\"VCE\"}"},
            {"role": "assistant", "content": "Yup"},
            {"role": "user", "content": "And for just France it should look like {\"city\": null,\"country\":\"France\",\"car rental\":null,\"IATA\":null}"},
            {"role": "assistant", "content": "Fine"},
            {"role": "user", "content": "If country and city name are the same it's ok to fill city and country with same values"},
            {"role": "assistant", "content": "Let's do it"}
        ]
        self._meta_text = ""
        if html:
            self.html = html
            self._soup = BeautifulSoup(self.html, 'html.parser')
        else:
            raise Exception("No html provided")
        
        if url:
            self.url = url
        else:
            raise Exception("No url provided")        

    def create_page_markup(self):
        #main flow to reach the result
        self.result = []
            
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
                        model=self._model,
                        messages=input
                    )
                    
            temp = completion['choices'][0]['message']['content']  # type: ignore
            try:
                temp = json.loads(temp)
                self.df.at[index, 'vertical'] = ', '.join(temp['Topics'])
            except:
                pass
    
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
        df = pd.DataFrame(columns=["sent_index","sentence","POI"])

        for sentense in self.gtp_markup:
            if "POIs" in sentense:
                for poi in sentense["POIs"]:
                    if len(poi) > 2:
                        row = []
                        if sentense["sentence"] in self.trafilatura_blob:
                            index = self.trafilatura_blob.index(sentense["sentence"])
                        else:
                            index = None
                        row.append(index)
                        row.append(sentense["sentence"])
                        row.append(poi)
                        df.loc[len(df.index)] = row  # type: ignore

        self.df = df
        
    
    def chat_gpt_markup(self):
        self.gtp_markup = []

        for chunk in self.chunks:
            input = []
            input = self.markup_default_messages + [{"role": "user", "content": "Awesome, now do it for:{0}".format(chunk)}]
            
            attempts = 0
            
            while attempts < self._max_regenerations:
                completion = openai.ChatCompletion.create(
                    model=self._model,
                    messages=input
                )
                
                a = completion['choices'][0]['message']['content']  # type: ignore
                err = completion['choices'][0]['finish_reason']  # type: ignore
                try:
                    a = json.loads(a)
                    for b in a:
                        self.gtp_markup.append(b)
                    break
                except:
                    attempts +=1

    def chunk_text(self):
        encoding = tiktoken.get_encoding("cl100k_base")
        encoding = tiktoken.encoding_for_model(self._model)

        # Tokenize the text
        tokens = encoding.encode(self.trafilatura_blob)
        
        # Divide the tokens into 7000-token chunks
        self.chunks = [tokens[i:i + self._max_tokens] for i in range(0, len(tokens), self._max_tokens)]

        # Decode the tokens back into text
        self.chunks = [encoding.decode(chunk) for chunk in self.chunks]
    
    def get_page_text(self):           
        self.useful_text = trafilatura.extract(self.html, include_links=False, include_comments=False, output_format='xml') 
        self.useful_text = ET.fromstring(self.useful_text)  # type: ignore
        blob = ""
        for element in self.useful_text.iter():
            if element.tag in ['p', 'item']:
                if element.text and element.text.strip():
                    blob += element.text.strip() + ' '
                for child in element:
                    blob += ET.tostring(child, encoding='unicode').strip() + ' '
        self.trafilatura_blob = blob            
     
    
    def _get_meta_text(self):        
        self._meta_text += self._soup.find('title').text + ' '  # type: ignore
        if self._soup.find('meta', attrs={'name': 'description'}):
            self._meta_text += self._soup.find('meta', attrs={'name': 'description'})['content'] + ' ' # type: ignore
        for tag in self._soup.find_all('meta'):
            if 'name' in tag.attrs and tag.attrs['name'].lower() in ['description', 'keywords', 'og:description', 'og:keywords']:
                self._meta_text +=  tag.attrs['content'] + ' '

    def get_meta_location_data(self) -> dict[str,bool]:
        self._get_meta_text()
        request =  self._get_meta_location_data_prompt+[{"role": "user", "content": f"Now do it for this text: {self._meta_text}"}]

        completion = openai.ChatCompletion.create(
            model=self._model,
            messages=request
        )

        loops_count = 0
        while loops_count<self._max_regenerations:            
            self._meta_location_data = json.loads(completion.choices[0].message['content']) # type: ignore
            if self._meta_location_data['country'] != None:
                break
            else:
                loops_count+=1

        if self._meta_location_data['country'] == None:  # type: ignore
            raise Exception("No country found") 
        
        return self._meta_location_data