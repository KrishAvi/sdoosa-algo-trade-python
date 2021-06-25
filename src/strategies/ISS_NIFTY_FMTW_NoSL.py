import logging
from datetime import datetime

from instruments.Instruments import Instruments
from models.Direction import Direction
from models.ProductType import ProductType
from strategies.BaseStrategy import BaseStrategy
from utils.Utils import Utils
from trademgmt.Trade import Trade
from trademgmt.TradeManager import TradeManager

breakout_point = None
# Each strategy has to be derived from BaseStrategy
class ISS_NIFTY_FMTW_NoSL(BaseStrategy):
  __instance = None

  @staticmethod
  def getInstance(): # singleton class
    if ISS_NIFTY_FMTW_NoSL.__instance == None:
      ISS_NIFTY_FMTW_NoSL()
    return ISS_NIFTY_FMTW_NoSL.__instance

  def __init__(self):
    if ISS_NIFTY_FMTW_NoSL.__instance != None:
      raise Exception("This class is a singleton!")
    else:
      ISS_NIFTY_FMTW_NoSL.__instance = self
    # Call Base class constructor
    super().__init__("ISS_NIFTY_FMTW_NoSL")
    # Initialize all the properties specific to this strategy
    self.productType = ProductType.MIS
    self.symbols = []
    self.slPercentage = 50
    self.targetPercentage = 0
    self.startTimestamp = Utils.getTimeOfToDay(15, 12, 0) # When to start the strategy. Default is Market start time
    self.stopTimestamp = Utils.getTimeOfToDay(15, 25, 0) # This is not square off timestamp. This is the timestamp after which no new trades will be placed under this strategy but existing trades continue to be active.
    self.squareOffTimestamp = Utils.getTimeOfToDay(15, 18, 0) # Square off time
    self.capital = 140000 # Capital to trade (This is the margin you allocate from your broker account for this strategy)
    self.leverage = 0
    self.maxTradesPerDay = 2 # (1 CE + 1 PE) Max number of trades per day under this strategy
    self.isFnO = True # Does this strategy trade in FnO or not
    self.capitalPerSet = 140000 # Applicable if isFnO is True (1 set means 1CE/1PE or 2CE/2PE etc based on your strategy logic)
    self.divisionfactor = 3 # Friday, Monday, Tuesday DF = 3 and Wednesday DF = 2
    self.roundedtoNearest = 50

  def canTradeToday(self):
    # Even if you remove this function canTradeToday() completely its same as allowing trade every day
    return True

  def process(self):

    if len(self.trades) > 0:

      for trade in self.trades:
        '''Capture Future value at every CE invoke and use it for PE square off '''
        if 'CE' in trade.tradingSymbol:
          global breakout_point
          breakout_point = self.getQuote(trade.futureSymbol)
          logging.info('%s: Breakout point update at CE invoke : %s and its value is %f', self.getName(),
                       trade.futureSymbol, breakout_point.lastTradedPrice)

      for tr in self.trades:
        if tr.squareOffCondtion is not True:
          if breakout_point.lastTradedPrice > tr.upperRangeSl:
            tr.squareOffCondtion = True  # This cancels existing SL ordre and place market order
            logging.info('%s: Stop loss hit: %s and its value %f breaks upper SL range %f', self.getName(),
                        tr.futureSymbol, breakout_point.lastTradedPrice, tr.upperRangeSl)
          elif breakout_point.lastTradedPrice < tr.lowerRangeSl:
            tr.squareOffCondtion = True  # This cancels existing SL ordre and place market order
            logging.info('%s: Stop loss hit: %s and its value %f breaks lower SL range %f', self.getName(),
                        tr.futureSymbol, breakout_point.lastTradedPrice, tr.lowerRangeSl)
          else:
            logging.info('%s: %s Stop loss monitoring: Its value is %f between %f and %f', self.getName(),
                        tr.futureSymbol,
                        breakout_point.lastTradedPrice, tr.lowerRangeSl, tr.upperRangeSl)


    now = datetime.now()
    if now < self.startTimestamp:
      return
    if len(self.trades) >= self.maxTradesPerDay:
      return

    # Get current market price of Nifty Future
    futureSymbol = Utils.prepareMonthlyExpiryFuturesSymbol('NIFTY')
    quote = self.getQuote(futureSymbol)
    if quote == None:
      logging.error('%s: Could not get quote for %s', self.getName(), futureSymbol)
      return

    FUTURESymbolSpotPrice = quote.lastTradedPrice #Capture Spot price before go for nearest value round off
    FUTURESymbol = futureSymbol #Capture future base symbol for monitoring in 30 sec trail SL task
    ATMStrike = Utils.getNearestStrikePrice(quote.lastTradedPrice, self.roundedtoNearest) #Rounded to nearest 100
    logging.info('%s: Nifty CMP = %f, ATMStrike = %d', self.getName(), quote.lastTradedPrice, ATMStrike)

    ATMCESymbol = Utils.prepareWeeklyOptionsSymbol("NIFTY", ATMStrike, 'CE')
    ATMPESymbol = Utils.prepareWeeklyOptionsSymbol("NIFTY", ATMStrike, 'PE')
    logging.info('%s: ATMCESymbol = %s, ATMPESymbol = %s', self.getName(), ATMCESymbol, ATMPESymbol)
    # create trades
    self.generateTrades(ATMCESymbol, ATMPESymbol,FUTURESymbol,FUTURESymbolSpotPrice)

  def generateTrades(self, ATMCESymbol, ATMPESymbol,FUTURESymbol,FUTURESymbolSpotPrice):
    numLots = self.calculateLotsPerTrade()
    quoteATMCESymbol = self.getQuote(ATMCESymbol)
    quoteATMPESymbol = self.getQuote(ATMPESymbol)
    if quoteATMCESymbol == None or quoteATMPESymbol == None:
      logging.error('%s: Could not get quotes for option symbols', self.getName())
      return

    #Calculate lower and upper range for stop loss ordre
    slFactor = Utils.roundToNSEPrice((quoteATMCESymbol.lastTradedPrice + quoteATMPESymbol.lastTradedPrice)/self.divisionfactor)
    upperRangeSl = FUTURESymbolSpotPrice + slFactor
    lowerRangeSl = FUTURESymbolSpotPrice - slFactor

    self.generateTrade(ATMCESymbol, numLots, quoteATMCESymbol.lastTradedPrice,
                       FUTURESymbol,FUTURESymbolSpotPrice,upperRangeSl,lowerRangeSl)
    self.generateTrade(ATMPESymbol, numLots, quoteATMPESymbol.lastTradedPrice,
                       FUTURESymbol,FUTURESymbolSpotPrice,upperRangeSl,lowerRangeSl)
    logging.info('%s: Trades generated.', self.getName())

  def generateTrade(self, optionSymbol, numLots, lastTradedPrice,
                    futureSymbol,futureSymbolSpotPrice,upperRangeSl,lowerRangeSl):
    trade = Trade(optionSymbol)
    trade.futureSymbol = futureSymbol
    trade.futureSymbolSpotPrice = futureSymbolSpotPrice
    trade.lowerRangeSl = lowerRangeSl
    trade.upperRangeSl = upperRangeSl
    trade.strategy = self.getName()
    trade.isOptions = True
    trade.direction = Direction.SHORT # Always short here as option selling only
    trade.productType = self.productType
    trade.placeMarketOrder = True
    trade.requestedEntry = lastTradedPrice
    trade.timestamp = Utils.getEpoch(self.startTimestamp) # setting this to strategy timestamp
    
    isd = Instruments.getInstrumentDataBySymbol(optionSymbol) # Get instrument data to know qty per lot
    trade.qty = isd['lot_size'] * numLots
    
    #trade.stopLoss = Utils.roundToNSEPrice(trade.requestedEntry + trade.requestedEntry * self.slPercentage / 100)
    trade.stopLoss = 0 #No stoploss order
    trade.target = 0 # setting to 0 as no target is applicable for this trade

    trade.intradaySquareOffTimestamp = Utils.getEpoch(self.squareOffTimestamp)
    trade.squareOffCondtion = False #Initialise square off conndition for monitoring
    # Hand over the trade to TradeManager
    TradeManager.addNewTrade(trade)

  def shouldPlaceTrade(self, trade, tick):
    # First call base class implementation and if it returns True then only proceed
    if super().shouldPlaceTrade(trade, tick) == False:
      return False
    # We dont have any condition to be checked here for this strategy just return True
    return True


