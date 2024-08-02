import requests
import matplotlib.pyplot as plt


#add your api key below, note FMP allows free API key access (250 API calls per day) when you sign up. see README.md
api_key = 'IHs6ny612Q0HxcgjsQBlUwfW7bMX27EF'

#add the ticker of the company's income statement you would like to view
company = 'FB'
#add the amount of years of income statement data you would like to view
years = 2

income_statement = requests.get(f'https://financialmodelingprep.com/api/v3/income-statement/{company}?limit={years}&apikey={api_key}')
income_statement = income_statement.json()

print(income_statement)