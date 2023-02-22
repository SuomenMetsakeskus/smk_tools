from osgeo import gdal,gdal_array
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib as mpl
import requests,tempfile,os
import numpy as np
import sys,subprocess
import pandas as pd
from math import sqrt,pow

from waterLine import raster2Array
from qgis.core import *
from qgis.analysis import QgsNativeAlgorithms
from qgis.PyQt.QtCore import QVariant
import processing


def fillSink(elev):
    

    dem = processing.run("saga:fillsinkswangliu",
                   {'ELEV':elev,
                    'FILLED':'TEMPORARY_OUTPUT',
                    'FDIR':'TEMPORARY_OUTPUT',
                    'WSHED':'TEMPORARY_OUTPUT',
                    'MINSLOPE':0.1})
    
    return dem['FILLED']

def calcMassFlux(elev,rusle,ls,water):
    

    
    mf = processing.run("saga:flowaccumulationrecursive", 
                   {'ELEVATION':elev,
                    'SINKROUTE':None,
                    'WEIGHTS':ls,
                    'FLOW':'TEMPORARY_OUTPUT',
                    'VAL_INPUT':None,
                    'VAL_MEAN':'TEMPORARY_OUTPUT',
                    'ACCU_MATERIAL':rusle,
                    'ACCU_TARGET':water,
                    'ACCU_TOTAL':'TEMPORARY_OUTPUT',
                    'ACCU_LEFT':'TEMPORARY_OUTPUT',
                    'ACCU_RIGHT':'TEMPORARY_OUTPUT',
                    'FLOW_UNIT':1,
                    'TARGETS':None,
                    'FLOW_LENGTH':'TEMPORARY_OUTPUT',
                    'WEIGHT_LOSS':'TEMPORARY_OUTPUT',
                    'METHOD':2,'CONVERGENCE':1.1,
                    'NO_NEGATIVES':False})
    
    return mf['ACCU_TOTAL']


def getMassSum(mf,waterborder):
    mf_array = raster2Array(mf,1)
    water_arr = raster2Array(waterborder,1)
    
    mf_array = np.where(water_arr>0,mf_array,0)
    massSum = np.sum(mf_array)
    
    return massSum

def array2raster(in_array,map_raster):
    tempd = tempfile.TemporaryFile()
    tempd = tempd.name+'.tif'
    
    gdal_array.SaveArray(in_array.astype("float32"),tempd,"GTiff",map_raster)

    return tempd

def getEffect(mf,mfmin,mfmax):
    ret_max = mfmax - mfmin
    added_material = mf - mfmin
    reserved_material = mfmax - mf
    cost = round((reserved_material / ret_max) * 100,1)
    
    return ret_max,added_material,reserved_material,cost

def raster2vector(in_rast,data):
    
    vectn = processing.run("gdal:polygonize", 
        {'INPUT':in_rast,
        'BAND':1,
        'FIELD':'DN',
        'EIGHT_CONNECTEDNESS':False,
        'EXTRA':'',
        'OUTPUT':"TEMPORARY_OUTPUT"})
    
    vect = QgsVectorLayer(vectn['OUTPUT'],"vyohyke","ogr")
    arealist = [feat.geometry().area() for feat in vect.getFeatures() if feat['DN']==1]
    namelist = list(data.columns)
    for i in namelist:
        vect.dataProvider().addAttributes([QgsField(i,QVariant.Double)])
        vect.updateFields()
    
    with edit(vect):
        for feat in vect.getFeatures():
            if feat['DN'] == 0:
                vect.deleteFeature(feat.id())

            if max(arealist) - feat.geometry().area() > 100:
                vect.deleteFeature(feat.id())

            for i in namelist:
                datac = data[[i]]
                #print (datac.iloc[0,0])
                feat[i] = float(datac.iloc[0,0])
            
            geom = feat.geometry()
            buffer = geom.buffer(10, 5)
            buffer = buffer.buffer(-10,5)
            feat.setGeometry(buffer)

            vect.updateFeature(feat)
    
    return vect

def getBufferzone(rasters,clipraster,waterborder,dist,target):
    
    #change the rasters to numpy array
    demfill = fillSink(rasters[4])
    zraster = raster2Array(rasters[0],1)
    eucarr = raster2Array(rasters[0],2)
    cuttarr = raster2Array(clipraster,1)
    lsarr = raster2Array(rasters[0],3)
    
    rusarr = raster2Array(rasters[1],1)
    rusarr = np.where(rusarr>0,rusarr/10000*4,0.01)
    rus = array2raster(rusarr,rasters[4])
    
    #change necessary value units and filter to clip raster
    zzone = np.where(cuttarr==1,zraster,0)
    z = zzone[zzone>0]
    
    lsarr = np.where(lsarr>0,lsarr / 200.0,0) #ls facto only to cliparea
    
    
    ls_max = np.where(cuttarr==1,1,lsarr)
    ls_min = lsarr #min and max scenarios
    
    ls_max = array2raster(ls_max,rasters[4])
    ls_min = array2raster(ls_min,rasters[4])
    
    mfmin = calcMassFlux(demfill,rus,ls_min,rasters[3])
    mfmax = calcMassFlux(demfill,rus,ls_max,rasters[3])
    mfmin = getMassSum(mfmin,waterborder)
    mfmax = getMassSum(mfmax,waterborder)
    
    t=0
    for i in range(5,100,5):
        zp = np.percentile(z,i)
        ls_fact = np.where((cuttarr==1) & (zraster>zp) & (eucarr>=dist[0]),1,lsarr)
        ls_fact = np.where((cuttarr==1) & (ls_fact<1) & (eucarr>=dist[2]),1,ls_fact)
    
        mdist = np.where((cuttarr==1) & (ls_fact<1),eucarr,0)
        mdist = mdist[mdist>0]
        mdist = np.mean(mdist)*2
        
        ls = array2raster(ls_fact,rasters[4])
        #print (mdist)
        #showRaster(ls)
        
        mf = calcMassFlux(demfill,rus,ls,rasters[3])
        mf = getMassSum(mf,waterborder)
        
        effect = getEffect(mf,mfmin,mfmax)
        if (effect[3] > target and mdist > dist[1]):
            break
        
    bzone = np.where((cuttarr==1) & (ls_fact<1),1,0)
    bzone = array2raster(bzone,rasters[1])
    
    dataset = {'massflux_max':[mfmax],
                'retention_max':[effect[0]],
                'natural_massflux':[mfmin],
                'massflux':[mf],
                'material_reserved':[effect[2]],
                'material_added':[effect[1]],
                'distance_mean':[mdist],
                'cost':[effect[3]]}
    
    df = pd.DataFrame(dataset)
    res = raster2vector(bzone,df)
    
    return res