from osgeo import gdal_array,gdal
import tempfile
import numpy as np
from math import sqrt,pow
import os
#from waterLine import raster2Array
from qgis.core import *
from qgis.PyQt.QtCore import QVariant
import processing


def raster2vector(in_rast,data):
    """transfrom input buffer zone raster to vector"""
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
            #raster value 0 means out
            if feat['DN'] == 0:
                vect.deleteFeature(feat.id())
            
            #delete small parts
            if max(arealist) - feat.geometry().area() > max(arealist) /1.4:
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

def raster2vector2(in_rast,data):
    """transfrom input buffer zone raster to vector"""
    vectn = processing.run("gdal:polygonize", 
        {'INPUT':in_rast,
        'BAND':1,
        'FIELD':'DN',
        'EIGHT_CONNECTEDNESS':False,
        'EXTRA':'',
        'OUTPUT':'TEMPORARY_OUTPUT'})
    
    vect = QgsVectorLayer(vectn['OUTPUT'],"vyohyke","ogr")
    #arealist = [feat.geometry().area() for feat in vect.getFeatures() if feat['DN']==1]
    namelist = list(data.columns)
    for i in namelist:
        vect.dataProvider().addAttributes([QgsField(i,QVariant.Double)])
        vect.updateFields()
    
    #ids = [(i.id(),i) for i in vect.getFeatures()]
    #fs = [i for i in]
    geom = [i.geometry().buffer(15,5) for i in vect.getFeatures()]
    g=geom[0]
    for i in geom:
        geo = i.combine(g)
         
    c = 0
    with edit(vect):
        for feat in vect.getFeatures():
            if c == 0:

                for i in namelist:
                    datac = data[[i]]
                    print (datac.iloc[0,0])
                    feat[i] = float(datac.iloc[0,0])
            
                #geom = feat.geometry()
                #buffer = geom.buffer(15, 5)
                buffer = geo.buffer(-14,5)
                feat.setGeometry(buffer)
                feat['pinta_ala'] = round(buffer.area()/10000,2)
                vect.updateFeature(feat)
                c = 1
            else:
                vect.deleteFeature(feat.id())
            vect.updateFeature(feat)
    return vect

def cleanGeom(vector):
    """cleans input vector geometry by buffering algorithm"""
    #vector = QgsVectorLayer(vector,"vect","ogr")

    with edit(vector):
        for feat in vector.getFeatures():
            geom = feat.geometry()
            buffer = geom.buffer(10,5)
            buffer = buffer.buffer(-9,5)
            feat.setGeometry(buffer)

            vector.updateFeature(feat)

def clipRaster(in_raster,band,clip_raster,band_clip):
    """clip raster by other raster"""
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

def array2raster(in_array,map_raster):
    tempd = tempfile.TemporaryFile()
    tempd = tempd.name+'.tif'
    
    gdal_array.SaveArray(in_array.astype("float32"),tempd,"GTiff",map_raster)

    return tempd