import logging
from datetime import datetime

from instruments.Instruments import Instruments
from models.Direction import Direction
from models.ProductType import ProductType
from strategies.BaseStrategy import BaseStrategy
from utils.Utils import Utils
from trademgmt.Trade import Trade
from trademgmt.TradeManager import TradeManager

slPtsSysc = 0
sum_premium = 0
# Each strategy has to be derived from BaseStrategy
class ISS_NIFTY_ExpiryDay(BaseStrategy):
  __instance = None

  @staticmethod
  def getInstance(): # singleton class
    if ISS_NIFTY_ExpiryDay.__instance == None:
      ISS_NIFTY_ExpiryDay()
    return ISS_NIFTY_ExpiryDay.__instance

  def __init__(self):
    if ISS_NIFTY_ExpiryDay.__instance != None:
      raise Exception("This class is a singleton!")
    else:
      ISS_NIFTY_ExpiryDay.__instance = self
    # Call Base class constructor
    super().__init__("ISS_NIFTY_ExpiryDay")
    # Initialize all the properties specific to this strategy
    self.productType = ProductType.MIS
    self.symbols = []
    self.slPercentage = 50
    self.targetPercentage = 0
    self.startTimestamp = Utils.getTimeOfToDay(10, 4, 0) # When to start the strategy. Default is Market start time
    self.stopTimestamp = Utils.getTimeOfToDay(14, 0, 0) # This is not square off timestamp. This is the timestamp after which no new trades will be placed under this strategy but existing trades continue to be active.
    self.squareOffTimestamp = Utils.getTimeOfToDay(15, 4, 0) # Square off time
    self.capital = 140000 # Capital to trade (This is the margin you allocate from your broker account for this strategy)
    self.leverage = 0
    self.maxTradesPerDay = 2 # (1 CE + 1 PE) Max number of trades per day under this strategy
    self.isFnO = True # Does this strategy trade in FnO or not
    self.capitalPerSet = 140000 # Applicable if isFnO is True (1 set means 1CE/1PE or 2CE/2PE etc based on your strategy logic)
    self.slRunnningPercentage = 20 # Expiry day total premium collected running SL percentage
    self.roundedtoNearest = 50 #Rounded to nearest 100 or 50

  def canTradeToday(self):
    # Even if you remove this function canTradeToday() completely its same as allowing trade every day
    return True

  def process(self):
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
    slFactor = quoteATMCESymbol.lastTradedPrice + quoteATMPESymbol.lastTradedPrice
    slFactorPercentage = Utils.roundToNSEPrice(slFactor * self.slRunnningPercentage / 100)

    #Collected premiumum SL running percentage value is less than 10 points then cap to 10 points
    if slFactorPercentage < 10:
      slFactorPercentage = 10

    runningSL = slFactor + slFactorPercentage
    global slPtsSysc
    global sum_premium
    slPtsSysc = runningSL # Initilalisation starting SL
    sum_premium = slFactor #Initilalisation of Sum premium
    #upperRangeSl = FUTURESymbolSpotPrice + slFactor
    #lowerRangeSl = FUTURESymbolSpotPrice - slFactor

    self.generateTrade(ATMCESymbol, numLots, quoteATMCESymbol.lastTradedPrice,
                       FUTURESymbol,FUTURESymbolSpotPrice,runningSL,ATMPESymbol)
    self.generateTrade(ATMPESymbol, numLots, quoteATMPESymbol.lastTradedPrice,
                       FUTURESymbol,FUTURESymbolSpotPrice,runningSL,ATMCESymbol)
    logging.info('%s: Trades generated.', self.getName())

  def generateTrade(self, optionSymbol, numLots, lastTradedPrice,
                    futureSymbol,futureSymbolSpotPrice,runningSL,optionSymbolPair):
    trade = Trade(optionSymbol)
    trade.futureSymbol = futureSymbol
    trade.futureSymbolSpotPrice = futureSymbolSpotPrice
    trade.runningSL = runningSL
    trade.optionSymbolPair = optionSymbolPair
    trade.strategy = self.getName()
    trade.isOptions = True
    trade.direction = Direction.SHORT # Always short here as option selling only
    trade.productType = self.productType
    trade.placeMarketOrder = True
    trade.requestedEntry = lastTradedPrice
    trade.timestamp = Utils.getEpoch(self.startTimestamp) # setting this to strategy timestamp
    
    isd = Instruments.getInstrumentDataBySymbol(optionSymbol) # Get instrument data to know qty per lot
    trade.qty = isd['lot_size'] * numLots
    
    trade.stopLoss = Utils.roundToNSEPrice(trade.requestedEntry + trade.requestedEntry * self.slPercentage / 100)
    trade.target = 0 # setting to 0 as no target is applicable for this trade

    trade.intradaySquareOffTimestamp = Utils.getEpoch(self.squareOffTimestamp)
    trade.squareOffCondtion = False  # Initialise square off conndition for monitoring
    # Hand over the trade to TradeManager
    TradeManager.addNewTrade(trade)

  def shouldPlaceTrade(self, trade, tick):
    # First call base class implementation and if it returns True then only proceed
    if super().shouldPlaceTrade(trade, tick) == False:
      return False
    # We dont have any condition to be checked here for this strategy just return True
    return True

  def getTrailingSL(self, trade):
    if trade == None:
      return 0
    if trade.entry == 0:
      return 0
    lastTradedPrice = TradeManager.getLastTradedPrice(trade.tradingSymbol)
    if lastTradedPrice == 0:
      return 0
    '''
    At Every CE involke,
      1) Capture both CE & PE premium 
      2) Calculate Stop loss value store for PE Trade 
      3) Check premium collected stop loss percent is 5 points less than previous value
          if YES update SL
          else Keep old SL
      4) Save updated SL value for PE Trade
    At Every PE invoke
      1)Update SL captured during CE
    
    At very invoke
    If Sum_premium > SL
      Square off.
    '''
    if 'CE' in trade.tradingSymbol:
      optionSymbolPair = self.getQuote(trade.optionSymbolPair)
      global sum_premium
      sum_premium = optionSymbolPair.lastTradedPrice + lastTradedPrice
      new_runningSL = sum_premium + Utils.roundToNSEPrice(sum_premium * self.slRunnningPercentage / 100)
      profitPoints = int(trade.runningSL - new_runningSL)
      if profitPoints >= 5:
        logging.info('%s: %s Stop loss premium updatde from %f to %f',
                     self.getName(), trade.tradingSymbol, trade.runningSL, new_runningSL)
        trade.runningSL = new_runningSL
        global slPtsSysc
        slPtsSysc = new_runningSL
    elif 'PE' in trade.tradingSymbol:
      trade.runningSL = slPtsSysc

    trailSL = 0
    if sum_premium > trade.runningSL:
      trade.squareOffCondtion = True  #square off
      logging.info('%s: %s Stop loss hit as sum of premium = %f excedes trailing SL = %f ',
                   self.getName(), trade.tradingSymbol, sum_premium,trade.runningSL )
    else:
      logging.info('%s: %s Stop loss monitoring: Sum of premium = %f not excedes trailing SL = %f ',
                   self.getName(), trade.tradingSymbol, sum_premium, trade.runningSL)
    return trailSL

