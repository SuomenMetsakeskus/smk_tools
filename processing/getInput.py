import requests,tempfile
from math import sqrt,pow
from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsVectorLayer,QgsField,QgsFeature


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

    test = requests.get(wmsurl,params,allow_redirects=True)
    respo = test.content
    f = open(tempd,"wb")
    f.write(respo)
    f.close()
    
    return tempd

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
