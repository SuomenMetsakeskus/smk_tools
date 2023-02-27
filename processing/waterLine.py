from osgeo import gdal,gdal_array
import os
import numpy as np
import pandas as pd
from math import sqrt,pow

from qgis.core import *
from qgis.PyQt.QtCore import QVariant
from getInput import getBboxWmsFormat
import processing
from fcFunctions import array2raster,raster2vector,clipRaster,raster2Array,cleanGeom

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


def snap2water(waterraster,area):
    waterarr = raster2Array(waterraster,1)
    waterarr = np.where(waterarr>1,1,0)

    water = array2raster(waterarr,waterraster)

    data = {'cutarea':[1]}
    dat = pd.DataFrame(data)
    water = raster2vector(water,dat)
    
    snapped = processing.run("native:snapgeometries",
                             {'INPUT':area,
                              'REFERENCE_LAYER':water,'TOLERANCE':10,
                              'BEHAVIOR':1,
                              'OUTPUT':'TEMPORARY_OUTPUT'})
    
    cleanGeom(snapped['OUTPUT'])

    return snapped['OUTPUT']

def rasterizeVector(in_layer,gdal_extent,cells):
    
    output = os.path.dirname(os.path.realpath(in_layer.sourceName()))
    output = os.path.join(output,"rasterized.tif")


    processing.run("gdal:rasterize",
                        {'INPUT':in_layer,
                        'FIELD':'',
                        'BURN':1,
                        'USE_Z':False,
                        'UNITS':1,
                        'WIDTH':cells,
                        'HEIGHT':cells,
                        'EXTENT':gdal_extent,
                        'NODATA':0,
                        'OPTIONS':'',
                        'DATA_TYPE':5,
                        'INIT':None,
                        'INVERT':False,
                        'EXTRA':'',
                        'OUTPUT':output})

    return output


def getWaterline(rasters,leimikko):
    bbox = getBboxWmsFormat(leimikko)
    ss = bbox[0].split(',')
    extent = str(round(int(ss[0])-100,-1))+","+str(round(int(ss[2])+100,-1))+","+str(round(int(ss[1])-100,-1))+","+str(round(int(ss[3])+100,-1))+" ["+str(bbox[1])+"]"
    
    leimikko = snap2water(rasters[3],leimikko)
    vraster = processRaster(rasters[3]) #vesistörajan määritys

    leimraster = rasterizeVector(leimikko,extent,2)
    vrast_clip = clipRaster(vraster,1,leimraster,1) # rajataan leimikkoon
    #leimraster = clipRaster()
    leimraster = clipRaster(leimraster,1,rasters[0],2)

    return vrast_clip,leimraster