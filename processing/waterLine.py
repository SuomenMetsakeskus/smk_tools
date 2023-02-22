from osgeo import gdal,gdal_array
import os
import numpy as np
import pandas as pd
from math import sqrt,pow

from qgis.core import *
from qgis.PyQt.QtCore import QVariant
from getInput import getBboxWmsFormat
import processing


def calcFocal(in_array,etai):

    dat =pd.DataFrame(in_array)
    vert = dat
    ijlist = []
    for i in range(0-etai,etai):
        for j in range(0-etai,etai):
            e = sqrt(pow(i,2)+pow(j,2))
            if e <=etai:
                ijlist.append((i,j))
    
    for i in ijlist:
        df = dat.shift(i[0],axis=0)
        df = df.shift(i[1],axis=1)
        vert = pd.concat([vert,df]).max(level=0)
    t = []
    t.append(vert)
    t = np.array(t)

    return t

def processRaster(input):
    
    rastOut = input[0:-4]+"hh.tif"
    rast = gdal.Open(input)
    
    rastb = rast.GetRasterBand(1)
    rastA = rastb.ReadAsArray()
    rastA = np.where(rastA>0,rastA,0)
    
    focal = calcFocal(rastA,2)
    huip = np.where(focal-rastA==2,1,0)
    gdal_array.SaveArray(huip.astype("float32"),rastOut,"GTiff",rast)
    
    return rastOut



def clipRaster(in_raster,band,clip_raster,band_clip):
    
    output = os.path.dirname(os.path.realpath(in_raster))
    output = os.path.join(output,"clipped.tif")
    
    
    in_arr = raster2Array(in_raster,band)
    cl_arr = raster2Array(clip_raster,band_clip)
    
    in_arr = np.where((cl_arr>0) & (in_arr>0),in_arr,0)
    
    gdal_array.SaveArray(in_arr.astype("float32"),output,"GTiff",in_raster)
    
    return output

def raster2Array(in_raster,band):
    rast = gdal.Open(in_raster)
    rastB = rast.GetRasterBand(band)
    rastA = rastB.ReadAsArray()

    return rastA

def rasterizeVector(in_layer,cells):
    #print ("jee")
    output = os.path.dirname(os.path.realpath(in_layer.sourceName()))
    output = os.path.join(output,"rasterized.tif")

    bbox = getBboxWmsFormat(in_layer)
    ss = bbox[0].split(',')
    extent = str(round(int(ss[0])-100,-1))+","+str(round(int(ss[2])+100,-1))+","+str(round(int(ss[1])-100,-1))+","+str(round(int(ss[3])+100,-1))+" ["+str(bbox[1])+"]"
    processing.run("gdal:rasterize",
                        {'INPUT':in_layer,
                        'FIELD':'',
                        'BURN':1,
                        'USE_Z':False,
                        'UNITS':1,
                        'WIDTH':cells,
                        'HEIGHT':cells,
                        'EXTENT':extent,
                        'NODATA':0,
                        'OPTIONS':'',
                        'DATA_TYPE':5,
                        'INIT':None,
                        'INVERT':False,
                        'EXTRA':'',
                        'OUTPUT':output})

    return output


def getWaterline(rasters,leimikko):

    vraster = processRaster(rasters[3]) #vesistörajan määritys

    leimraster = rasterizeVector(leimikko,2)
    vrast_clip = clipRaster(vraster,1,leimraster,1) # rajataan leimikkoon
    #leimraster = clipRaster()
    leimraster = clipRaster(leimraster,1,rasters[0],2)

    return vrast_clip,leimraster