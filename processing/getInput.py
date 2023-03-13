import requests,tempfile
from math import sqrt,pow
from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsVectorLayer,QgsField,QgsFeature
from osgeo import gdal
import numpy as np


def getBboxWmsFormat(in_feat:QgsVectorLayer):
    desc=in_feat.extent()
    x_min=int(desc.xMinimum())
    y_min=int(desc.yMinimum())
    x_max=int(desc.xMaximum())+1
    y_max=int(desc.yMaximum())+1
    srid=str(in_feat.crs().authid())
    exte = str(x_min)+","+str(y_min)+","+str(x_max)+","+str(y_max)
    witdth = x_max - x_min
    height = y_max - y_min
    
    return exte,srid,witdth,height

def getWater(input_polygon:QgsVectorLayer,taso):
    tempd = tempfile.TemporaryFile()
    tempd = tempd.name+str(taso)+'.tif'
    bbox = getBboxWmsFormat(input_polygon)
    
    ss = bbox[0].split(',')
    
    wmsurl = 'https://aineistot.metsakeskus.fi/metsakeskus/rest/services/Vesiensuojelu/'+taso+'/ImageServer/exportImage?'
    params = {"bbox":str(round(int(ss[0])-100,-1))+","+str(round(int(ss[1])-100,-1))+","+str(round(int(ss[2])+100,-1))+","+str(round(int(ss[3])+100,-1)),
                "bboxSR":3067,
                "size":str((round(int(ss[2])+100,-1)-round(int(ss[0])-100,-1))/2)+","+str((round(int(ss[3])+100,-1) - round(int(ss[1])-100,-1))/2),
                "imageSR":3067,
                "format":'tiff',
                "pixelType":"F32",
                "noData":-9999,
                "noDataInterpretation":"esriNoDataMatchAny",
                "interpolation":"+RSP_BilinearInterpolation",
                "f":"image"}

    try:
        respo= requests.get(wmsurl,params,allow_redirects=True)
        
        if respo.status_code != 200:
           info = "Cannot connect to "+str(taso)+ " data: "+str(wmsurl)
           infolevel = 3
        else:
            open(tempd,'wb').write(respo.content)
    
    except:
        info = "Cannot connect to "+str(taso)+ " data: "+str(wmsurl)
        infolevel = 3
    
        
    try:
        test = gdal.Open(tempd)
        test_b = test.GetRasterBand(1)
        test_a = test_b.ReadAsArray()
        if np.max(test_a) > 1:
            info = str(taso)+" data is ok!"
            infolevel = 1
            del test,test_b,test_a
        else:
           info = "Not able find "+str(taso)+" data from area: "+str(bbox[0])
           infolevel = 3
    except:
        info = "Not able find "+str(taso)+" data from area: "+str(bbox[0])
        infolevel = 3

    return tempd,info,infolevel

def feature2layer(feature):
    vl = QgsVectorLayer("Polygon", "temporary_pol","memory")
    pr = vl.dataProvider()
    # Enter editing mode
    vl.startEditing()
    pr.addAttributes( [QgsField("id",  QVariant.Int)])

    fet = QgsFeature()
    fet.setGeometry( feature.geometry())
    fet.setAttributes(feature.attributes())
    pr.addFeatures( [ fet ] )
    
    vl.commitChanges()
    vl.updateExtents()
    
    return vl
