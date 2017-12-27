import requests
import csv
import json
from pprint import pprint
from collections import namedtuple


url = "http://financials.morningstar.com/ajax/exportKR2CSV.html?t=%(exchange)s:%(ticker)s"
exchange = "XASX"


def create_url(ticker):
    return url % {"exchange": exchange, "ticker": ticker}


def requestcsv(session, url):
    result = session.get(url).content.decode('utf-8').splitlines()
    return result


def readcsv(data):
    return csv.reader(
        data,
        delimiter=','
    )


def get_financial(session, ticker):
    filename = 'cache/%s.csv' % ticker
    try:
        with open(filename, newline='') as cached:
            return cached.readlines()
    except FileNotFoundError:
        pass
    result = requestcsv(session, create_url(ticker))
    with open(filename, 'w') as write:
        write.write("\n".join(result))
    return result


Realtime = namedtuple('Realtime', ['price', 'eps', 'name'])
ShareData = namedtuple('ShareData', [
    'ticker',
    'realtime',
    'eps',
    'dividends'
])
RateResult = namedtuple('RateResult', [
    'rating',
    'dividend_valuation',
    'eps_valuation'
])


def find_realtime_stock(session, ticker):
    response = session.get('https://finance.google.com/finance?q=ASX:%s&output=json' % ticker)
    son = json.loads(response.content[6:-2].decode('unicode_escape'))
    return Realtime(price=son['l'], eps=son['eps'], name=son['name'])

def float_or_zero(string):
    return float(string) if string else 0

def valuate_anuity(sequence, discount=0.9, count=1):
    suming = 0
    for item in sequence:
        num = float_or_zero(item)
        suming += num * discount ** count
    return suming


def calculate_rating(data):
    cur_eps = float_or_zero(data.realtime.eps)
    eps_ann = valuate_anuity(data.eps) + cur_eps
    div_ann = valuate_anuity(data.dividends)
    price = float(data.realtime.price)
    if price == 0.0:
        return None
    return RateResult(
        rating=(min(eps_ann, div_ann) + cur_eps) / price ,
        dividend_valuation=div_ann,
        eps_valuation=eps_ann
    )


PresentRow = namedtuple('PresentRow', ['ticker', 'name', 'eps', 'price', 'rating'])

def main():
    session = requests.Session()
    parsed = readcsv(
        requestcsv(
            session,
            'http://www.asx.com.au/asx/research/ASXListedCompanies.csv'
        )
    )
    nohead = [row for row in parsed][3:]
    tickers = [row[1] for row in nohead]
    result = []
    i = 0
    for ticker in tickers:
        i += 1
        print('doing %s' % ticker)
        financial = get_financial(session, ticker)
        csv = [row for row in readcsv(financial)]
        if not csv:
            continue
        if csv == [['We’re sorry. There is no available information in our database to display.']]:
            continue

        try:
            data = ShareData(
                ticker=ticker,
                realtime=find_realtime_stock(session, ticker),
                eps=reversed(csv[8][1:-1]),
                dividends=reversed(csv[9][1:-1])
            )
        except json.decoder.JSONDecodeError:
            continue

        rating = calculate_rating(data)

        if rating:
            result.append(PresentRow(
                ticker=ticker,
                eps=data.realtime.eps,
                price=data.realtime.price,
                name=data.realtime.name,
                rating=rating
            ))
        if i > 5:
            break

    sorted_results = sorted(result, key=lambda it: -it.rating.rating)

    for result in sorted_results:
        price = float(result.price)
        def ratio(num):
            return (num/price)*100
        print("%(ticker)s: e%%%(percent-eps).1f\td%%%(percent-dividend).1f\tea%%%(percent-earnings).1f\t$%(price).5f,\tceps%(eps)s,\tdiv%(dividend).2f,\tea%(earnings).2f" % {
            'ticker': result.ticker,
            'percent-eps': ratio(float(result.eps)),
            'percent-dividend': ratio(result.rating.dividend_valuation),
            'percent-earnings': ratio(result.rating.eps_valuation),
            'price': price,
            'eps': result.eps,
            'dividend': result.rating.dividend_valuation,
            'earnings': result.rating.eps_valuation,
        })
      

if __name__ == "__main__":
    main()
