import requests,tempfile,json
from math import sqrt,pow
from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsVectorLayer,QgsField,QgsFeature
from osgeo import gdal
import numpy as np
#from qgis import processing


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

def doEsriParams(input_polygon:QgsVectorLayer):
    bbox = getBboxWmsFormat(input_polygon)
    ss = bbox[0].split(',')
    params = {"bbox":str(round(int(ss[0])-100,-1))+","+str(round(int(ss[1])-100,-1))+","+str(round(int(ss[2])+100,-1))+","+str(round(int(ss[3])+100,-1)),
                "bboxSR":bbox[1],
                "size":str((round(int(ss[2])+100,-1)-round(int(ss[0])-100,-1))/2)+","+str((round(int(ss[3])+100,-1) - round(int(ss[1])-100,-1))/2),
                "imageSR":3067,
                "format":'tiff',
                "pixelType":"F32",
                "noData":-9999,
                "noDataInterpretation":"esriNoDataMatchAny",
                "interpolation":"+RSP_BilinearInterpolation",
                "f":"image"}
    return params

def doWmsParams(input_polygon:QgsVectorLayer):
    bbox = getBboxWmsFormat(input_polygon)
    params = {'service':'wms',
          'request':'getMap',
         'bbox':bbox[0],
          'format':'image/geotiff',
          'width':bbox[2],
          'height':bbox[3],
          'layers':'CHM_newest',
          'srs':bbox[1]}
    return params

def doWcsParams(input_polygon:QgsVectorLayer,url,name):
    bbox = getBboxWmsFormat(input_polygon)
    ss = bbox[0].split(',')
    covId = 'paituli:luke_dtw_04'
    version = '2.0.0'
    sset1 = 'E('+ss[0]+','+ss[2]+')'
    sset2 = 'N('+ss[1]+','+ss[3]+')'
    params = {'service':'WCS',
        'request':'GetCoverage',
        'version':version,
        'coverageId':covId}
    url = url+'subset='+sset1+'&subset='+sset2
    
    return url,params

def doWfsParams(input_polygon:QgsVectorLayer,name:str,attributes:str):
    """This makes parameters for wfs-request of specific area
        inputs: 1. input_polygon as QgsVectorlayer , vector polygon QGS-format
                2. name as string,  layer name of service
                3, attributes as string, wanted attributes as comma separation eg. 'att1,att2,att3'"""
    bbox=getBboxWmsFormat(input_polygon)
    params = {'service':'wfs',
          'request':'getFeature',
          'typename':name,
            'propertyName':attributes,
          'bbox':bbox[0],
          'outputFormat':'json',
          'srsname':bbox[1]}
    
    return params

def doESRIfeatParams(input_polygon:QgsVectorLayer,name:str,attributes:str):
    """This makes parameters for esrifeature-request of specific area
        inputs: 1. input_polygon as QgsVectorlayer , vector polygon QGS-format
                2. name as string,  layer name of service
                3, attributes as string, wanted attributes as comma separation eg. 'att1,att2,att3'"""
    desc=input_polygon.extent()
    x_min=int(desc.xMinimum())
    y_min=int(desc.yMinimum())
    x_max=int(desc.xMaximum())+1
    y_max=int(desc.yMaximum())+1
    srid=str(input_polygon.crs().authid())
    srid=srid[5:]
    #print (srid)
    #input_polygon.set
    gparam = "geometryType=esriGeometryEnvelope&geometry="+str(x_min)+","+str(y_min)+","+str(x_max)+","+str(y_max)

    params = {"geometry":gparam,
                "geometryType":"esriGeometryEnvelope",
                "inSR":srid,
                "spatialRel":"esriSpatialRelIntersects",
                "outFields":attributes,
                "geometryPrecision":3,
                "outSR":srid,
                "f":"geojson"}
    return params

def getWebVectorLayer(input_polygon:QgsVectorLayer,url:str,name:str,attributes:str):
    tempd = tempfile.TemporaryFile()
    tempd = tempd.name+'.geojson'
    if url.endswith("wfs?") or url.endswith("ows?"):
        params = doWfsParams(input_polygon,name,attributes)
    else:
        url = url + '/query?'
        params = doESRIfeatParams(input_polygon,name,attributes)
    
    respo_layer =""
    try:
        respo = requests.get(url,params,allow_redirects=True)
        print (respo.status_code)
        if respo.status_code != 200:
            info = "Not getting connection to forest data: "+str(url)
            print (respo.raise_for_status())
            infolevel = 3
        else:
            respo_js = respo.json()
            with open(tempd, "w") as outfile:
                json.dump(respo_js,outfile)
            
            respo_layer = QgsVectorLayer(tempd,name,"ogr")
            if respo_layer.featureCount() == 0:
                info = "Not able to find data from area"
                infolevel = 3
            else:
                respo_layer = processing.run("native:fixgeometries",{'INPUT':respo_layer,'OUTPUT':'TEMPORARY_OUTPUT'})
                info = "Forest data is ok"
                infolevel = 1
    
    except Exception as e:
        print (e)
        info = "Not getting connection to forest data: "+str(url)
        infolevel = 3
    
    
    
    
    return respo_layer['OUTPUT'],info,infolevel

def getWebRasterLayer(input_polygon:QgsVectorLayer,url:str,name:str):
    tempd = tempfile.TemporaryFile()
    tempd = tempd.name+'.tif'
    
    if url.endswith("ImageServer"):
        url = url + "/exportImage?"
        params = doEsriParams(input_polygon)
    elif url.endswith("ows?") or url.endswith("wms?"):
        params = doWmsParams(input_polygon)
    else:
        prep = doWcsParams(input_polygon,url,name)
        params = prep[1]
        url = prep[0]
        

    try:
        respo= requests.get(url,params,allow_redirects=True)
        
        if respo.status_code != 200:
           info = "Cannot connect to data: "+str(url)
           infolevel = 3
        else:
            open(tempd,'wb').write(respo.content)
    
    except Exception as e:
        info = str(e)
        infolevel = 3
    
        
    try:
        test = gdal.Open(tempd)
        test_b = test.GetRasterBand(1)
        test_a = test_b.ReadAsArray()
        if np.max(test_a) > 1.0:
            info =  "data is ok!"
            infolevel = 1
            del test,test_b,test_a
        else:
           info = "Not able find data from area"
           infolevel = 3
    except Exception as e:
        info = str(e)
        infolevel = 3

    return tempd,info,infolevel

def getProtectedSites(in_feat):
    tempd = tempfile.TemporaryFile()
    tempd = tempd.name+".geojson"
   
    params = doESRIfeatParams(in_feat,"pros","OBJECTID,Nimi")
 
    inurl = "https://paikkatieto.ymparisto.fi/arcgis/rest/services/INSPIRE/SYKE_SuojellutAlueet/MapServer/"

    ser = ['2','3','4','7','8','9'] #rajataan natura- ja ls-alueisiin
    proS = []
    
    for i in ser:
        inu = inurl+i+"/query?"
        x = requests.get(inu,params)
        rjs = json.loads(x.content)
        #te = tempd+'11.geojson'
        with open(tempd, "w") as outfile:
            json.dump(rjs,outfile)
        try:
            fix_ls = processing.run("native:fixgeometries",{'INPUT':tempd+'|geometrytype=Polygon','OUTPUT':'TEMPORARY_OUTPUT'})
            proS.append(fix_ls['OUTPUT'])
        except:
            print ("no service")
    
    if len(proS)>0:
        #fix_nat = processing.run("native:fixgeometries", {'INPUT':tempd+'|geometrytype=Polygon','OUTPUT':'TEMPORARY_OUTPUT'})
        fix = processing.run("native:mergevectorlayers", {'LAYERS':proS,'CRS':None,'OUTPUT':'TEMPORARY_OUTPUT'})
    
        #fix = processing.run("native:dissolve", {'INPUT':fix['OUTPUT'], 'OUTPUT':'TEMPORARY_OUTPUT'})
        return fix['OUTPUT']
    else:
        return None
    


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