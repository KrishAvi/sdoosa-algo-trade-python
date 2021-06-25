import logging
import threading
import time

from instruments.Instruments import Instruments
from trademgmt.TradeManager import TradeManager

from strategies.SampleStrategy import SampleStrategy
from strategies.BNFORB30Min import BNFORB30Min
from strategies.OptionSelling import OptionSelling
from strategies.ShortStraddleBNF import ShortStraddleBNF

from strategies.ShortStraddleNIFTY import ShortStraddleNIFTY

from strategies.ISS_NIFTY_FMTW import ISS_NIFTY_FMTW
from strategies.ISS_NIFTY_FMTW_NoSL import ISS_NIFTY_FMTW_NoSL

from strategies.ISS_NIFTY_ExpiryDay import ISS_NIFTY_ExpiryDay
from strategies.ISS_NIFTY_ExpiryDay_NoSL import ISS_NIFTY_ExpiryDay_NoSL

#from Test import Test

class Algo:
  isAlgoRunning = None

  @staticmethod
  def startAlgo():
    if Algo.isAlgoRunning == True:
      logging.info("Algo has already started..")
      return
    
    logging.info("Starting Algo...")
    Instruments.fetchInstruments()

    # start trade manager in a separate thread
    tm = threading.Thread(target=TradeManager.run)
    tm.start()

    # sleep for 2 seconds for TradeManager to get initialized
    time.sleep(2)

    # start running strategies: Run each strategy in a separate thread
    #threading.Thread(target=SampleStrategy.getInstance().run).start()
    #threading.Thread(target=BNFORB30Min.getInstance().run).start()
    #threading.Thread(target=OptionSelling.getInstance().run).start()
    #threading.Thread(target=ShortStraddleBNF.getInstance().run).start()


    #30cagr
    threading.Thread(target=ShortStraddleNIFTY.getInstance().run).start()

    #Alok jain
    #threading.Thread(target=ISS_NIFTY_FMTW.getInstance().run).start()
    threading.Thread(target=ISS_NIFTY_FMTW_NoSL.getInstance().run).start()

    #threading.Thread(target=ISS_NIFTY_ExpiryDay.getInstance().run).start()
    #threading.Thread(target=ISS_NIFTY_ExpiryDay_NoSL.getInstance().run).start()

    
    Algo.isAlgoRunning = True
    logging.info("Algo started.")
