import requests
import matplotlib.pyplot as plt


#add your api key below, note FMP allows free API key access (250 API calls per day) when you sign up. see README.md
api_key = 'IHs6ny612Q0HxcgjsQBlUwfW7bMX27EF'

#add the ticker of the company's income statement you would like to view
company = 'AAPL'
#add the amount of years of income statement data you would like to view
years = 10


income_statement = requests.get(f'https://financialmodelingprep.com/api/v3/income-statement/{company}?limit={years}&apikey={api_key}')
income_statement = income_statement.json()


# uncomment line directly below to pull all income statement lines
# print(income_statement)

# uncomment line directly below if you want an individual line item from the income statement printed. here is an example of a revenue comparison. the number 0 represents the last full year. in this case it is 2023's revenue.
# print(income_statement[0]['revenue'])

# some other examples or items you can pull
# print(income_statement[0]['grossProfit'])
# print(income_statement[0]['eps'])
# print(income_statement[0]['ebitda'])

revenues = list(reversed([income_statement[i]['revenue'] for i in range(len(income_statement))]))
profits = list(reversed([income_statement[i]['grossProfit'] for i in range(len(income_statement))]))

plt.plot(revenues, label='Revenue')
plt.plot(profits, label='Profit')
plt.title('Revenue & Profit')
plt.legend(loc = 'upper right')
plt.show()

