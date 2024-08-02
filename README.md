# incomeStatementAnalyzer

IS-Tool
A simple, no-fuss way to extract public companies' income statements, compare them YOY, play with individual statement pieces, and even visualize individual statement items in a plot graph!

Getting Started

To get a local copy up and running follow these simple example steps:

This tool is run on [python](https://www.python.org/), with [pip](https://pip.pypa.io/en/stable/installation/) as the command interface. Once you have pip installed, use 'pip install' command to install 'requests' and 'pyplot'

Data provided by [Financial Modeling Prep](https://financialmodelingprep.com/developer/docs/). Click link and sign up for a free API Key. in the main.py file, populate your API key.

In the main.py file, you can choose a ticker for any public company. This will go in the 'company' line. In the 'years' line, put how many years of income statements you would like. For example, inputting '1' will give the last full year that has pasts' income statement. Inputting '2' in 2024 will pull 2023 and 2022 income statement data.

When you are ready to run the program, in your terminal, type 'python3 main.py'. Enjoy!
