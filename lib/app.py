import os
import pandas as pd

import os.path
import site
site.addsitedir(os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from lib.markupper import Markupper
from lib.helpers import get_html


dataset = ['https://www.chasingthedonkey.com/best-things-to-do-in-croatia/']

sumamries = pd.DataFrame()
markups = pd.DataFrame()

for url in dataset:
    try:
        # getting page html
        html = get_html(url)
        markupper = Markupper(url,html)
        
        # getting page summary
        row  = pd.DataFrame({**{"url":url},**markupper.get_meta_location_data()},index=[0])
        sumamries = pd.concat([sumamries,row])

        # getting page markup
        # markups = pd.concat([markups, markupper.create_page_markup()], ignore_index=True)
    
    except Exception as e:   
        print(str(e))

print(sumamries)
sumamries.to_csv('sumamries.csv', index=False)

print(markups)
markups.to_csv('markups.csv', index=False)