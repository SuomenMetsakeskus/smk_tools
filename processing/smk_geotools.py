from osgeo import gdal,gdal_array
import os,sys,tempfile
from math import sqrt
import pandas as pd
import numpy as np
from qgis.PyQt.QtCore import QVariant
from qgis import processing
#import processing
from qgis.core import QgsVectorLayer,QgsField,QgsFeature,edit,QgsApplication
from qgis.analysis import QgsInterpolator,QgsIDWInterpolator,QgsGridFileWriter

#for developing
QgsApplication.setPrefixPath(QgsApplication.prefixPath(), True)
qgs = QgsApplication([], False)
qgs.initQgis()
sys.path.append(os.path.join(QgsApplication.prefixPath(),"python\plugins"))
import processing
from processing.core.Processing import Processing
Processing.initialize()
#import processing
#from processing.core.Processing import Processing
#Processing.initialize()
#import processing
from qgis.analysis import QgsNativeAlgorithms



def feature2Layer(feat,buffer):
    """
    This creates vectorlayer from feature. You can buffer feature at specific distance
    """
    vl = QgsVectorLayer("Polygon", "temporary_points", "memory")
    pr = vl.dataProvider()

    # add fields
    vl.startEditing()
    pr.addAttributes(feat.fields())
    vl.updateFields() # tell the vector layer to fetch changes from the provider

    fet = QgsFeature()
    fet.setGeometry(feat.geometry().buffer(buffer,5))
    #fet.setGeometry(feat.geometry())
    fet.setAttributes(feat.attributes())
    pr.addFeatures([fet])

    vl.updateExtents()
    vl.commitChanges()

    return vl

def copyRaster2(inp,outp):
    """
    This is simple raster copy
    """
    os.popen('copy '+inp+' '+outp)


def focalMaximaCHM(input_raster,distance):
    """
    This calculates focal maximum value by specific search distance
    """
    
    rastOut = input_raster[0:-4]+"hh.tif"
    chm = gdal.Open(input_raster)
    
    chmB = chm.GetRasterBand(1)
    chmA = chmB.ReadAsArray()
    chmA = (chmA-126)*0.232 #vaihe 1

    focal = calcFocal(chmA,distance) #vaihe 2
    huip = focal - chmA
    huip = np.where(focal-chmA==0,chmA,np.NaN)
    huip = np.where(huip>=5,huip*10,np.NaN) #vaihe3
    gdal_array.SaveArray(huip.astype("float32"),rastOut,"GTiff",chm)

    return rastOut

def calcFocal(in_array,distance):
    """
    This loops raster array and looks all cell values of each cell which are within distance values from cell
    """

    dat =pd.DataFrame(in_array)
    vert = dat
    ijlist = []
    for i in range(0-distance,distance):
        for j in range(0-distance,distance):
            e = sqrt(pow(i,2)+pow(j,2))
            if e <=distance:
                ijlist.append((i,j))
    
    #print (ijlist)

    for i in ijlist:
        df = dat.shift(i[0],axis=0)
        df = df.shift(i[1],axis=1)
        vert = pd.concat([vert,df]).max(level=0)
    t = []
    t.append(vert)
    t = np.array(t)

    return t

def delNulls(input_vector):
    """
    This deletes null-values of treemap  
    """
    input_vector = QgsVectorLayer(input_vector, "puukartta", "ogr")
    

    feats = input_vector.getFeatures()
    dfeat=[]
    
    for feat in feats:
        if feat['CHM'] < 0:
            dfeat.append(feat.id())

    input_vector.dataProvider().deleteFeatures(dfeat)


def createTreeMap(input_chm,distance):
    """
    This creates tree map as point layer from chm raster. Algorithm is based on local maxima at specific search distance
    """
    #tempd = tempfile.TemporaryFile()
    #tempd = tempd.name+'.shp'
    focalMax = focalMaximaCHM(input_chm,distance)
    tempd = processing.run("gdal:polygonize", {'INPUT':focalMax,'BAND':1,'FIELD':'CHM','EIGHT_CONNECTEDNESS':False,'EXTRA':'','OUTPUT':'TEMPORARY_OUTPUT'})
    
    delNulls(tempd['OUTPUT'])
    tempd = processing.run("native:centroids", {'INPUT':tempd['OUTPUT'],'ALL_PARTS':False,'OUTPUT':'TEMPORARY_OUTPUT'})
    processing.run("native:createspatialindex", {'INPUT':tempd['OUTPUT']})

    return tempd['OUTPUT']

def addFieldValue(in_feat:QgsVectorLayer,fieldname:str,fieldvalue:float):
    """
    This adds field with given value to the vector layer
    """
    fix = processing.run("native:fixgeometries", {'INPUT':in_feat,'OUTPUT':'TEMPORARY_OUTPUT'})
    fix['OUTPUT'].dataProvider().addAttributes([QgsField(fieldname,QVariant.Double)])
    fix['OUTPUT'].updateFields()
    with edit(fix['OUTPUT']):
        for feat in fix['OUTPUT'].getFeatures():
            feat['leimikko']=fieldvalue

            fix['OUTPUT'].updateFeature(feat)
    
    return fix['OUTPUT']

def joinIntersection(inlayer,joinlayer,joinfields):
    """
    This join by spatial intersection two layers
    """
    joined = processing.run("native:joinattributesbylocation", {'INPUT':inlayer,'JOIN':joinlayer,'PREDICATE':[0],'JOIN_FIELDS':joinfields,'METHOD':0,'DISCARD_NONMATCHING':False,'PREFIX':'','OUTPUT':'TEMPORARY_OUTPUT'})

    return joined['OUTPUT']

def hsAnalysis(in_feat,fieldname):
    """
    This interpolate field value of point layer. Input layer need to be QgsVectorLayer format
    and fieldname string format. The analysis save interpolated values to new field of point layer with prefix 'HS_'
    """
    #in_feat = QgsVectorLayer(in_feat,"tt","ogr")

    tempd = tempfile.TemporaryFile()
    tempd = tempd.name+'.tif'

    ext = in_feat.extent()
    idx = in_feat.dataProvider().fieldNameIndex(fieldname)

    layer_data = QgsInterpolator.LayerData()
    layer_data.source = in_feat 
    layer_data.zCoordInterpolation = False
    layer_data.interpolationAttribute = idx
    layer_data.mInputType = 1


    idw_interpolator = QgsIDWInterpolator([layer_data])
    res = 1
    ncols = int( ( ext.xMaximum() - ext.xMinimum() ) / res )
    nrows = int( (ext.yMaximum() - ext.yMinimum() ) / res)

    out  = QgsGridFileWriter(idw_interpolator,tempd,ext,ncols,nrows)
    out.writeFile()

    out = processing.run("native:rastersampling", {'INPUT':in_feat,'RASTERCOPY':tempd,'COLUMN_PREFIX':'HS_','OUTPUT':'TEMPORARY_OUTPUT'})
 
    #hs = processing.run("qgis:idwinterpolation",{'INTERPOLATION_DATA':in_name+"::~::0::~::"+str(idx)+"::~::0",'DISTANCE_COEFFICIENT':2,'EXTENT':ext,'PIXEL_SIZE':1,'OUTPUT':'TEMPORARY_OUTPUT'})
    
    return out['OUTPUT']