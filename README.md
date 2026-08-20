# Algorithmic Trading Signals Pipeline

## Project Overview

This project is an automated, event-driven algorithmic trading signals pipeline built entirely on serverless cloud architecture. It is designed to automatically download, process, and analyze historical financial market data for a basket of 76 ETFs every day after the market closes to identify technical signals for the next trading session.

The backend pipeline ingests historical daily price data, computes technical indicators, and evaluates trading logic. When a buy or sell signal is detected, the system generates a chart and archives the results into a data lake and database.

The project features a simple React user interface. When a user accesses the dashboard, an API queries the database and generates pre-signed S3 URLs, allowing the user to instantly review the latest trading signals and their corresponding charts from anywhere.

## Architecture & Technologies Used

### Infrastructure & Orchestration

* **Terraform:** Provisions, configures, and manages the entire AWS infrastructure as code, ensuring reproducible and version-controlled environments.
* **AWS Step Functions:** Orchestrates the backend workflow. It processes all 76 ETF tickers in parallel.
* **Docker & Amazon ECR:** Containerizes the serverless compute environments, specifically to compile and support data science libraries.
* **Amazon EventBridge:** Triggers the Step Functions every weekday shortly after market close without manual intervention.

### Compute & API Layer

* **AWS Lambda:** Provides event-driven, serverless compute for the entire backend. The architecture is split into microservices: `ingestor`, `analyzer`, `publisher`, `aggregator`, and `api_handler`.
* **Amazon API Gateway:** Acts as the secure front door for the React dashboard, routing HTTP fetch requests directly to the `api_handler` Lambda function.

### Data & Storage

* **Amazon S3:** Acts as the central storage repository. It stores raw historical CSVs, processed technical indicator data, and generated Plotly charts.
* **Amazon DynamoDB:** Stores the structured daily trading signals in NoSQL.

### Event-Driven Notifications

* **Amazon SNS:** Once the `aggregator` Lambda function finishes compiling the day's trading signals, it formats a summary report and publishes it to an SNS topic so subscribers get an immediate email.

### Frontend & Delivery

* **React / Vite / Tailwind CSS:** Serves as a basic UI framework for the frontend.
* **Amazon CloudFront & Route 53:** Distributes and caches the React application globally on a custom subdomain.

### Data Science & Backend Stack

* **Python 3.11:** The core language for all backend Lambda microservices.
* **Pandas & NumPy:** For high-performance data manipulation and time-series analysis.
* **TA-Lib (Technical Analysis Library):** Computes financial indicators.
* **Plotly & Kaleido:** Generates the advanced, interactive candlestick charts and exports them headlessly to high-resolution static images.
* **yfinance & Boto3:** Handles historical market data ingestion and programmatic communication with AWS services.

## How to Use It

### 1-Configure the global variables

**terraform.tfvars:** These variables are necessary in the main.tf scripts

* **aws_profile:** The name of the IAM profile for the SSO session. It must have administrative access permissions in order to create the AWS resources needed.
* **subscriber_email:** The email address of the person who will be notified when the pipeline runs every day.

### 2-Configure the Stock Symbols

**symbols.json:** Contains the following ETFs. You can edit and change it to your liking:

#### U.S. Broad Market & Style ETFs


| Ticker   | ETF Name                              | Primary Country Exposure | Primary Sector / Focus               |
| -------- | ------------------------------------- | ------------------------ | ------------------------------------ |
| **SPY**  | SPDR S&P 500 ETF Trust                | United States (~99.5%)   | Large-cap U.S. equities (S&P 500)    |
| **SPYG** | SPDR Portfolio S&P 500 Growth ETF     | United States (~98.5%)   | Large-cap U.S. growth stocks         |
| **QQQ**  | Invesco QQQ Trust                     | United States (~97%)     | Nasdaq-100 (large-cap tech & growth) |
| **DIA**  | SPDR Dow Jones Industrial Average ETF | United States (~99.9%)   | 30 blue-chip U.S. industrial stocks  |
| **IWM**  | iShares Russell 2000 ETF              | United States (~89–98%) | U.S. small-cap equities              |

#### U.S. Sector & Industry ETFs


| Ticker   | ETF Name                                      | Primary Country Exposure | Primary Sector / Focus                                  |
| -------- | --------------------------------------------- | ------------------------ | ------------------------------------------------------- |
| **XLE**  | Energy Select Sector SPDR ETF                 | United States (100%)     | Energy (oil, gas, consumable fuels)                     |
| **XLP**  | Consumer Staples Select Sector SPDR ETF       | United States            | Consumer staples (food, beverages, household products)  |
| **XLF**  | Financial Select Sector SPDR ETF              | United States            | Financials (banks, insurance, capital markets)          |
| **XLV**  | Health Care Select Sector SPDR ETF            | United States            | Health care (equipment, pharma, biotech)                |
| **XLU**  | Utilities Select Sector SPDR ETF              | United States            | Utilities (electric, water, gas)                        |
| **XLY**  | Consumer Discretionary Select Sector SPDR ETF | United States            | Consumer discretionary (retail, hospitality, auto)      |
| **XHB**  | SPDR S&P Homebuilders ETF                     | United States            | Homebuilders (consumer cyclical ~61%, industrials ~37%) |
| **XBI**  | SPDR S&P Biotech ETF                          | United States            | Biotechnology (healthcare ~100%)                        |
| **ITA**  | iShares U.S. Aerospace & Defense ETF          | United States            | Aerospace & defense (industrials ~100%)                 |
| **CIBR** | First Trust NASDAQ Cybersecurity ETF          | United States / Global   | Cybersecurity (technology ~94–95%)                     |
| **VNQ**  | Vanguard Real Estate ETF                      | United States            | Real estate (REITs ~98–99%)                            |
| **PGF**  | Invesco Financial Preferred ETF               | United States            | Financial preferred securities                          |

#### International & Regional ETFs


| Ticker   | ETF Name                               | Primary Country Exposure                                           | Primary Sector / Focus           |
| -------- | -------------------------------------- | ------------------------------------------------------------------ | -------------------------------- |
| **VXUS** | Vanguard Total International Stock ETF | Global ex-U.S. (Japan, UK, Canada, Taiwan, China, etc.)            | Total international equities     |
| **EFA**  | iShares MSCI EAFE ETF                  | Developed ex-U.S./Canada (Japan, UK, France, Germany, etc.)        | Developed international equities |
| **EEM**  | iShares MSCI Emerging Markets ETF      | Emerging markets (Taiwan, South Korea, China, India, Brazil, etc.) | Emerging market equities         |
| **ILF**  | iShares Latin America 40 ETF           | Latin America (Brazil ~67%, Mexico ~26%)                           | Latin American equities          |
| **SMH**  | VanEck Semiconductor ETF               | United States (~82%), Taiwan (~10%), Netherlands (~6%)             | Semiconductor industry           |

#### Single-Country ETFs (Americas)


| Ticker   | ETF Name                    | Primary Country Exposure |
| -------- | --------------------------- | ------------------------ |
| **EWC**  | iShares MSCI Canada ETF     | Canada (~98%)            |
| **EWW**  | iShares MSCI Mexico ETF     | Mexico (~99.6%)          |
| **EWZ**  | iShares MSCI Brazil ETF     | Brazil (~84–96%)        |
| **ECH**  | iShares MSCI Chile ETF      | Chile (~92–100%)        |
| **EPU**  | iShares MSCI Peru ETF       | Peru (~44–50%)          |
| **COLO** | Global X MSCI Colombia ETF  | Colombia (~77–82%)      |
| **ARGT** | Global X MSCI Argentina ETF | Argentina (~72–73%)     |

#### Single-Country ETFs (Europe)


| Ticker   | ETF Name                        | Primary Country Exposure  |
| -------- | ------------------------------- | ------------------------- |
| **EWU**  | iShares MSCI United Kingdom ETF | United Kingdom (~93–95%) |
| **EWG**  | iShares MSCI Germany ETF        | Germany (~99.4%)          |
| **EWQ**  | iShares MSCI France ETF         | France (~88–89%)         |
| **EWI**  | iShares MSCI Italy ETF          | Italy (~88–90%)          |
| **EWP**  | iShares MSCI Spain ETF          | Spain (~93–95%)          |
| **EWN**  | iShares MSCI Netherlands ETF    | Netherlands (~86–89%)    |
| **EWL**  | iShares MSCI Switzerland ETF    | Switzerland (~98.8%)      |
| **EWD**  | iShares MSCI Sweden ETF         | Sweden (~87–90%)         |
| **EWK**  | iShares MSCI Belgium ETF        | Belgium (~79–83%)        |
| **EWO**  | iShares MSCI Austria ETF        | Austria (~98%)            |
| **ENOR** | iShares MSCI Norway ETF         | Norway (~83–95%)         |
| **EFNL** | iShares MSCI Finland ETF        | Finland (~82–100%)       |
| **EDEN** | iShares MSCI Denmark ETF        | Denmark (~97%)            |
| **EIRL** | iShares MSCI Ireland ETF        | Ireland (~78–89%)        |
| **GREK** | Global X MSCI Greece ETF        | Greece (~93–95%)         |
| **EPOL** | iShares MSCI Poland ETF         | Poland (~83–98%)         |

#### Single-Country ETFs (Asia-Pacific)


| Ticker   | ETF Name                     | Primary Country Exposure |
| -------- | ---------------------------- | ------------------------ |
| **EWJ**  | iShares MSCI Japan ETF       | Japan (~100%)            |
| **EWT**  | iShares MSCI Taiwan ETF      | Taiwan (~97%)            |
| **EWY**  | iShares MSCI South Korea ETF | South Korea (~100%)      |
| **EWA**  | iShares MSCI Australia ETF   | Australia (~100%)        |
| **EWS**  | iShares MSCI Singapore ETF   | Singapore (~91–92%)     |
| **EWH**  | iShares MSCI Hong Kong ETF   | Hong Kong (~84–93%)     |
| **GXC**  | SPDR S&P China ETF           | China (~69–94%)         |
| **INDA** | iShares MSCI India ETF       | India (~88–99%)         |
| **EIDO** | iShares MSCI Indonesia ETF   | Indonesia (~99%)         |
| **EWM**  | iShares MSCI Malaysia ETF    | Malaysia (~99.5%)        |
| **EPHE** | iShares MSCI Philippines ETF | Philippines (~91–100%)  |
| **THD**  | iShares MSCI Thailand ETF    | Thailand (~88–100%)     |
| **VNM**  | VanEck Vietnam ETF           | Vietnam (~96–99%)       |
| **ENZL** | iShares MSCI New Zealand ETF | New Zealand (~94–96%)   |

#### Single-Country ETFs (Middle East & Africa)


| Ticker  | ETF Name                      | Primary Country Exposure         |
| ------- | ----------------------------- | -------------------------------- |
| **EZA** | iShares MSCI South Africa ETF | South Africa (~73–86%)          |
| **EIS** | iShares MSCI Israel ETF       | Israel (~91–98%)                |
| **UAE** | iShares MSCI UAE ETF          | United Arab Emirates (~78–100%) |
| **QAT** | iShares MSCI Qatar ETF        | Qatar (~81–101%)                |
| **TUR** | iShares MSCI Turkey ETF       | Turkey (~85–100%)               |
| **KSA** | iShares MSCI Saudi Arabia ETF | Saudi Arabia (~90–100%)         |
| **KWT** | iShares MSCI Kuwait ETF       | Kuwait (~92–100%)               |

#### Commodity & Currency ETFs


| Ticker   | ETF Name                                | Primary Country Exposure                                        | Primary Sector / Focus           |
| -------- | --------------------------------------- | --------------------------------------------------------------- | -------------------------------- |
| **GLD**  | SPDR Gold Trust                         | Global (physical gold held in London)                           | Gold bullion                     |
| **GDX**  | VanEck Gold Miners ETF                  | Global (North America ~79–81%, Australasia ~7–9%, Africa ~5%) | Gold mining equities             |
| **SLV**  | iShares Silver Trust                    | Global (physical silver held in London)                         | Silver bullion                   |
| **SIL**  | Global X Silver Miners ETF              | Global (Canada ~63%, U.S. ~18%, Mexico ~5%)                     | Silver mining equities           |
| **UUP**  | Invesco DB US Dollar Index Bullish Fund | United States                                                   | U.S. dollar vs. major currencies |
| **TLT**  | iShares 20+ Year Treasury Bond ETF      | United States (100%)                                            | Long-term U.S. Treasury bonds    |
| **IBIT** | iShares Bitcoin Trust                   | United States (domicile)                                        | Bitcoin                          |

#### Other / Specialized ETFs


| Ticker   | ETF Name              | Primary Country Exposure               | Primary Sector / Focus                  |
| -------- | --------------------- | -------------------------------------- | --------------------------------------- |
| **QTUM** | Defiance Quantum ETF  | Global (developed ~83%, emerging ~10%) | Quantum computing (technology ~79–85%) |
| **^VIX** | CBOE Volatility Index | N/A (index, not an ETF)                | Measures market volatility expectations |


### 4-Run the Terraform scripts (Command Prompt)

* **Authentication:** From the root folder, run "aws configure sso"
* **Execute the Terraform Pipeline:** Also from the root folder, run "terraform output api_endpoint"

### 5-Build the React Dashboard and host it on S3 (Command Prompt)

* **Configure the Endpoint:** In frontend/src/App.jsx, use the api endpoint from step 4 above in the API_ENDPOINT constant
* **Fix Dependencies:** Navigate to the frontend folder and run "npm install"
* **Build the Package:** Also from the frontend folder, run "npm run build"

