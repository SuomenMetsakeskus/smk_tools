from osgeo import gdal_array
import tempfile
import numpy as np
import pandas as pd
from math import sqrt,pow

from fcFunctions import raster2Array,array2raster,raster2vector
from qgis.core import *
from qgis.PyQt.QtCore import QVariant
import processing


def fillSink(elev):
    """repair input elevation raster that flows goes to lowest areas"""
    tempd = tempfile.TemporaryFile()
    tempd = tempd.name+'.tif'
    """
    processing.run("wbt:FillDepressions", 
                   {'dem':elev,
                    'fix_flats':True,
                    'flat_increment':None,
                    'max_depth':None,
                    'output':tempd})

    """
    processing.run("saga:fillsinkswangliu",
                   {'ELEV':elev,
                    'FILLED':tempd,
                    'FDIR':'TEMPORARY_OUTPUT',
                    'WSHED':'TEMPORARY_OUTPUT',
                    'MINSLOPE':0.1})
    
    return tempd

def calcMassFlux(elev,rusle,ls,water):
    """calculates massflux of input parameters. This will be change
    to saga-gis flowaccumulation massflux algorithm when published"""
    tempd = tempfile.TemporaryFile()
    tempd = tempd.name+'.tif'

    """
    processing.run("wbt:DInfMassFlux",
                   {'dem':elev,
                    'loading':rusle,
                    'efficiency':ls,
                    'absorption':water,
                    'output':tempd})
    return tempd

    """
    mf = processing.run("saga:flowaccumulationrecursive", 
                   {'ELEVATION':elev,
                    'SINKROUTE':None,
                    'WEIGHTS':ls,
                    'FLOW':'TEMPORARY_OUTPUT',
                    'VAL_INPUT':None,
                    'VAL_MEAN':'TEMPORARY_OUTPUT',
                    'ACCU_MATERIAL':rusle,
                    'ACCU_TARGET':water,
                    'ACCU_TOTAL':tempd,
                    'ACCU_LEFT':'TEMPORARY_OUTPUT',
                    'ACCU_RIGHT':'TEMPORARY_OUTPUT',
                    'FLOW_UNIT':1,
                    'TARGETS':None,
                    'FLOW_LENGTH':'TEMPORARY_OUTPUT',
                    'WEIGHT_LOSS':'TEMPORARY_OUTPUT',
                    'METHOD':2,'CONVERGENCE':1.1,
                    'NO_NEGATIVES':False})
    
    return tempd
    

def getMassSum(mf,waterborder):
    """calculates massflux sum of the input waterline raster"""
    mf_array = raster2Array(mf,1)
    water_arr = raster2Array(waterborder,1)
    
    mf_array = np.where(water_arr>0,mf_array,0)
    massSum = np.sum(mf_array)
    
    return massSum


def getEffect(mf,mfmin,mfmax):
    """"calculates water protection attributes"""
    ret_max = mfmax - mfmin
    added_material = mf - mfmin
    reserved_material = mfmax - mf
    cost = round((reserved_material / ret_max) * 100,1)
    
    return ret_max,added_material,reserved_material,cost

def getBufferzone(rasters,clipraster,waterborder,dist,target):
    """Increase buffer zone area when distance and target are satisfied"""
    #change the rasters to numpy array
    demfill = fillSink(rasters[3])
    zraster = raster2Array(rasters[0],1)
    eucarr = raster2Array(rasters[0],2)
    cuttarr = raster2Array(clipraster,1)
    lsarr = raster2Array(rasters[0],3)

    #change necessary value units and filter to clip raster
    zzone = np.where(cuttarr==1,zraster,0)
    z = zzone[zzone>0]
    
    lsarr = np.where(lsarr>0,lsarr / 200.0,0) #ls facto only to cliparea
    ls_max = np.where(cuttarr==1,1,lsarr)
    ls_min = lsarr #min and max scenarios

    rusarr = raster2Array(rasters[1],1)
    rusarr = np.where(rusarr>0,rusarr/10000*4,0.01) 
    rus = array2raster(rusarr,rasters[3])

    ls_max = array2raster(ls_max,rasters[3])
    ls_min = array2raster(ls_min,rasters[3])
    
    mfmin = calcMassFlux(demfill,rus,ls_min,rasters[2])
    mfmax = calcMassFlux(demfill,rus,ls_max,rasters[2])
    mfmin = round(getMassSum(mfmin,waterborder),2)
    mfmax = round(getMassSum(mfmax,waterborder),2)
    t=0
    #don't remove comments below. Future version will use those parts.
    for i in range(5,100,5):
        zp = np.percentile(z,i)
        ls_fact = np.where((cuttarr==1) & (zraster>zp) & (eucarr>=dist[0]),1,lsarr)
        #ls_fact = np.where((cuttarr==1) & (ls_fact<1) & (eucarr>=dist[2]),1,ls_fact)
    
        mdist = np.where((cuttarr==1) & (ls_fact<1),eucarr,0)
        mdist = mdist[mdist>0]
        mdist = round(np.mean(mdist)*2,1)
        #rus = np.where(rusarr>0,rusarr/10000*4*ls_fact,0.01)
        #rus = array2raster(rus,rasters[4])
        ls = array2raster(ls_fact,rasters[3])
        #print (mdist)
        #showRaster(ls)
        
        #mf = calcMassFlux(demfill,rus,ls,rasters[3])
        #mf = round(getMassSum(mf,waterborder),2)
        
        #effect = getEffect(mf,mfmin,mfmax)
        if (mdist >= dist[1] and target[0] == False):
            break
        #elif (target[0]==True and mdist>=dist[1] and effect[3]>=target[1]):
         #   break

    bzone = np.where((cuttarr==1) & (ls_fact<1),1,0)
    bzone = array2raster(bzone,rasters[1])
    
    dataset = {'kiintoainekuorma_max':[mfmax],
                'pidatyksen_max':[mfmax-mfmin],
                'luonnonhuuhtouma':[mfmin],
                #'kiintoainekuorma':[mf],
                #'pidatettykiintoaine':[effect[2]],
                #'lisattykiintoaine':[effect[1]],
                #'pidatysprosentti':[effect[1]],
                'keskileveys':[mdist]}
    
    df = pd.DataFrame(dataset)
    res = raster2vector(bzone,df)
    """return buffer zone as vector layer with dataset attributes"""
    return res