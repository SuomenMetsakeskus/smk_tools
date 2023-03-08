# -*- coding: utf-8 -*-
from base64 import decode
from osgeo import gdal,gdal_array
import pandas as pd
import numpy as np
from math import sqrt,pow
import json
from qgis.PyQt.QtCore import QVariant
from paras_2 import decay_tree_potential,NP_retention
import matplotlib.pyplot as plt
from qgis import processing
from qgis.analysis import QgsInterpolator,QgsIDWInterpolator,QgsGridFileWriter
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsVectorLayer,edit)
import os,requests,tempfile

#testitaso ="S:/Luontotieto/QGIS_plugin_test/testitasot.gpkg|layername=inputLeimikko"
#testitaso = "S:/Luontotieto/QGIS_plugin_test/testitasot.gpkg|layername=testitasov1"
#testitaso = QgsVectorLayer(testitaso,"testi","ogr")

def feature2Layer(feat,buffer):
    vl = QgsVectorLayer("Polygon", "temporary_points", "memory")
    pr = vl.dataProvider()

    # add fields
    pr.addAttributes([QgsField("id",  QVariant.Int)])
    vl.updateFields() # tell the vector layer to fetch changes from the provider

    # add a feature
    fet = QgsFeature()
    fet.setGeometry(feat.geometry().buffer(buffer,5))
    #fet.setCrs(3067)
    fet.setAttributes([1])
    pr.addFeatures([fet])

    # update layer's extent when new features have been added
    # because change of extent in provider is not propagated to the layer
    vl.updateExtents()

    return vl

def proBuffer(input):    
    """
    if os.path.isfile(output):
        os.remove(output)
        form = ['.shx','.dbf','prj']
        for i in form:
            f = output[:-4]+i
            if os.path.isfile(f):
                os.remove(f)"""

    out = processing.run("native:buffer", \
        {'INPUT':input,\
        'DISTANCE':100,\
        'SEGMENTS':5,\
        'END_CAP_STYLE':0,\
        'JOIN_STYLE':0,
        'MITER_LIMIT':2,\
        'DISSOLVE':False,\
        'OUTPUT':'TEMPORARY_OUTPUT'})

    return out['OUTPUT']

def getBboxWmsFormat(in_feat):
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

#def dataValid(stand,fgrid,dtw,)

def getRaster(in_feat):
    bbox = getBboxWmsFormat(in_feat)
    tempd = tempfile.TemporaryFile()
    tempd = tempd.name+'.tif'

    #print (tempd)


    wmsurl = 'https://rajapinnat.metsaan.fi/geoserver/Avoinmetsatieto/CHM_newest/ows?'
    params = {'service':'wms',
          'request':'getMap',
         'bbox':bbox[0],
          'format':'image/geotiff',
          'width':bbox[2],
          'height':bbox[3],
          'layers':'CHM_newest',
          'srs':bbox[1]}

    try:
        respo = requests.get(wmsurl,params,allow_redirects=True)
        if respo.status_code != 200:
            info = "Cannot connect to chm data: "+str(wmsurl)
            infolevel = 3
        else:
            open(tempd,'wb').write(respo.content)
            info = "CHM file is ok"
            infolevel = 1

    except:
        info = "Cannot connect to chm data: "+str(wmsurl)
        infolevel = 3

    

    try:
        test = gdal.Open(tempd)
        test_b = test.GetRasterBand(1)
        test_a = test_b.ReadAsArray()
        if np.max(test_a) > 10:
            info = "CHM file is ok"
            infolevel = 1
            del test,test_b,test_a
        else:
            info = "Cannot connect to chm data: "+str(wmsurl)
            infolevel = 3
    except:
        info = "Cannot connect to chm data: "+str(wmsurl)
        infolevel = 3
    
    #ras = arcpy.Raster(tempd)
    return tempd,info,infolevel

def getDTW(in_feat,service):
    #QgsMessageLog.logMessage("Kokeillaan viestiä: "+str(in_feat),level=Qgis.Info)
    bbox = getBboxWmsFormat(in_feat)
    ss = bbox[0].split(',')

    tempd = tempfile.TemporaryFile()
    tempd = tempd.name+'.tif'
    
    if service == "dtw":
        wmsurl = 'https://paituli.csc.fi/geoserver/paituli/wcs?'
        covId = 'paituli:luke_dtw_04'
        version = '2.0.0'
        sset1 = 'E('+ss[0]+','+ss[2]+')'
        sset2 = 'N('+ss[1]+','+ss[3]+')'
        params = {'service':'WCS',
            'request':'GetCoverage',
            'version':version,
            'coverageId':covId}
        wmsurl = wmsurl+'subset='+sset1+'&subset='+sset2
    
    #tee oma moduuli tästä
    else:
        wmsurl = 'https://aineistot.metsakeskus.fi/metsakeskus/rest/services/Vesiensuojelu/euclidean/ImageServer/exportImage?'
        params = {"bbox":ss[0]+","+ss[1]+","+ss[2]+","+ss[3],
                "bboxSR":3067,
                "imageSR":3067,
                "format":'tiff',
                "pixelType":"S16",
                "noData":0,
                "noDataInterpretation":"esriNoDataMatchAny",
                "interpolation":"+RSP_BilinearInterpolation",
                "f":"image"}
    try:
        respo= requests.get(wmsurl,params,allow_redirects=True)
        
        if respo.status_code != 200:
           info = "Cannot connect to water data: "+str(wmsurl)
           infolevel = 2
        else:
            open(tempd,'wb').write(respo.content)
    
    except:
        info = "Cannot connect to water data: "+str(wmsurl)
        infolevel = 2
    
        
    try:
        test = gdal.Open(tempd)
        test_b = test.GetRasterBand(1)
        test_a = test_b.ReadAsArray()
        if np.max(test_a) > 1:
            info = "Water data is ok!"
            infolevel = 1
            del test,test_b,test_a
        else:
           info = "Not able find water data from area: "+str(bbox[0])
           infolevel = 2
    except:
        info = "Not able find water data from area: "+str(bbox[0])
        infolevel = 2

    return tempd,info,infolevel

def copyRaster2(inp,outp):
    os.popen('copy '+inp+' '+outp)

def processRaster(input):
    
    rastOut = input[0:-4]+"hh.tif"
    chm = gdal.Open(input)
    
    chmB = chm.GetRasterBand(1)
    chmA = chmB.ReadAsArray()
    chmA = (chmA-126)*0.232

    focal = calcFocal(chmA,3)
    huip = focal - chmA
    huip = np.where(focal-chmA==0,chmA,np.NaN)
    huip = np.where(huip>=5,huip*10,np.NaN)
    gdal_array.SaveArray(huip.astype("float32"),rastOut,"GTiff",chm)

    return rastOut
    #'OUTPUT':'TEMPORARY_OUTPUT'

    #chm = getRaster(buffer_area)

def calcFocal(in_array,etai):

    dat =pd.DataFrame(in_array)
    vert = dat
    ijlist = []
    for i in range(0-etai,etai):
        for j in range(0-etai,etai):
            e = sqrt(pow(i,2)+pow(j,2))
            if e <=etai:
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
#def getEuclidean(in_feat,)

def vectorCHM(input):

    """if os.path.isfile(out):
        os.remove(out)
        form = ['.shx','.dbf','prj']
        for i in form:
            f = out[:-4]+i
            if os.path.isfile(f):
                os.remove(f)"""
    
    #tempd = tempfile.TemporaryFile()
    #tempd = tempd.name+'.shp'

    tempd = processing.run("gdal:polygonize", {'INPUT':input,'BAND':1,'FIELD':'CHM','EIGHT_CONNECTEDNESS':False,'EXTRA':'','OUTPUT':'TEMPORARY_OUTPUT'})
    
    delNulls(tempd['OUTPUT'])
    tempd = processing.run("native:centroids", {'INPUT':tempd['OUTPUT'],'ALL_PARTS':False,'OUTPUT':'TEMPORARY_OUTPUT'})
    processing.run("native:createspatialindex", {'INPUT':tempd['OUTPUT']})

    return tempd['OUTPUT']

def delNulls(input):
    input = QgsVectorLayer(input, "puukartta", "ogr")
    

    feats = input.getFeatures()
    dfeat=[]
    
    for feat in feats:
        if feat['CHM'] < 0:
            dfeat.append(feat.id())

    input.dataProvider().deleteFeatures(dfeat)

def joinForestData(in_treemap,joinfeat,joinfields):
    
    joined = processing.run("native:joinattributesbylocation", {'INPUT':in_treemap,'JOIN':joinfeat,'PREDICATE':[0],'JOIN_FIELDS':joinfields,'METHOD':0,'DISCARD_NONMATCHING':False,'PREFIX':'','OUTPUT':'TEMPORARY_OUTPUT'})

    return joined['OUTPUT']

def getFeatureFromWfs(in_area,typename):
    tempd = tempfile.TemporaryFile()
    tempd = tempd.name+'.geojson'

    
    
    bbox=getBboxWmsFormat(in_area)
    #print ("bb: "+bbox[0])
    in_url = 'http://rajapinnat.metsaan.fi/geoserver/Avoinmetsatieto/'+typename+'/ows?'
    params = {'service':'wfs',
          'request':'getFeature',
          'typename':typename,
          'bbox':bbox[0],
          'outputFormat':'json',
          'srsname':bbox[1]}
 
    
    
    try:
        respo = requests.get(in_url,params,allow_redirects=True)
        if respo.status_code != 200:
            info = "Not getting connection to forest data: "+str(in_url)
            infolevel = 3
        else:
            respo = respo.json()
            with open(tempd, "w") as outfile:
                json.dump(respo,outfile)
            
            respo = QgsVectorLayer(tempd,typename,"ogr")
            info = "Forest data is ok"
            infolevel = 1
    
    except:
        info = "Not getting connection to forest data: "+str(in_url)
        infolevel = 3
    
    
    if respo.featureCount() == 0:
        info = "Not able to find forest data from area: "+ str(bbox[0])
        infolevel = 3
    
    return respo,info,infolevel


def calculateDecayTreePotential(in_feat):
    
    in_feat.dataProvider().addAttributes([QgsField("dtree",QVariant.Double)])
    in_feat.updateFields()
    puuH = {"0":["MEANHEIGHTPINE",1],
            "1":["MEANHEIGHTSPRUCE",2],
            "2":["MEANHEIGHTDECIDUOUS",29]}

    with edit(in_feat):
        for feat in in_feat.getFeatures():
            maxH = [feat["MEANHEIGHTPINE"],feat["MEANHEIGHTSPRUCE"],feat["MEANHEIGHTDECIDUOUS"]]
            maxItem = max(maxH)
            maxH = puuH[str(maxH.index(maxItem))]
            dcp = decay_tree_potential('zone'+str(feat['PaajakoNro']))

            if feat['FERTILITYCLASS'] > 0 and feat[maxH[0]] >0:
                if feat['FERTILITYCLASS']>6:
                    para = dcp[6][int(maxH[1])]
                else:
                    para = dcp[int(feat['FERTILITYCLASS'])][int(maxH[1])]
                    
                d = maxH[0].replace("HEIGHT","DIAMETER")
                potvalue = np.poly1d(para)(int(feat[d]))
            else:
                potvalue=0

            if potvalue >1:
                feat["dtree"]=1.0
            else:
                feat["dtree"]=float(potvalue)
            
            
            in_feat.updateFeature(feat)
    
    normalizeValue(in_feat,"dtree")
    #normalizeValue(in_feat,"DTW_1")
        
def handleInput(in_feat):
    fix = processing.run("native:fixgeometries", {'INPUT':in_feat,'OUTPUT':'TEMPORARY_OUTPUT'})
    fix['OUTPUT'].dataProvider().addAttributes([QgsField("leimikko",QVariant.Double)])
    fix['OUTPUT'].updateFields()
    with edit(fix['OUTPUT']):
        for feat in fix['OUTPUT'].getFeatures():
            feat['leimikko']=1

            fix['OUTPUT'].updateFeature(feat)
    
    return fix['OUTPUT']

def geom2esri(in_area):

    tempd = tempfile.TemporaryFile()
    tempd = tempd.name+'.geojson'
    
    params = doESRIparam(in_area,"PaajakoNro,Nimi")
    inurl = "https://paikkatieto.ymparisto.fi/arcgis/rest/services/INSPIRE/SYKE_EliomaantieteellisetAlueet/MapServer/0/query?"

    x = requests.get(inurl,params)
    rjs = json.loads(x.content)

    with open(tempd, "w") as outfile:
        json.dump(rjs,outfile)

    fix = processing.run("native:fixgeometries", {'INPUT':tempd+'|geometrytype=Polygon','OUTPUT':'TEMPORARY_OUTPUT'})
    #respo = QgsVectorLayer(tempd,"testi","ogr")

    return fix['OUTPUT']

def doESRIparam(in_feat,fields):
    desc=in_feat.extent()
    x_min=int(desc.xMinimum())
    y_min=int(desc.yMinimum())
    x_max=int(desc.xMaximum())+1
    y_max=int(desc.yMaximum())+1
    srid=str(in_feat.crs().authid())
    srid=srid[5:]
    #print (srid)

    gparam = "geometryType=esriGeometryEnvelope&geometry="+str(x_min)+","+str(y_min)+","+str(x_max)+","+str(y_max)

    params = {"geometry":gparam,
                "geometryType":"esriGeometryEnvelope",
                "inSR":srid,
                "spatialRel":"esriSpatialRelIntersects",
                "outFields":fields,
                "geometryPrecision":3,
                "outSR":srid,
                "f":"geojson"}
    return params

def getProtectedSites(in_feat):
    tempd = tempfile.TemporaryFile()
    tempd = tempd.name+".geojson"
   
    params = doESRIparam(in_feat,"OBJECTID,Nimi")
 
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
    #print("jeij")

def calculateNPretention(in_feat):
    in_feat.dataProvider().addAttributes([QgsField("pRetent",QVariant.Double)])
    in_feat.updateFields()
    ret = NP_retention()
    with edit(in_feat):
        for feat in in_feat.getFeatures():
            if feat['euc_1'] is not None:
                feat['pRetent'] = ret['P']/feat['euc_1']
                
            in_feat.updateFeature(feat)
    
    normalizeValue(in_feat,'pRetent')


def simpson_di(data):
    N = sum(data.values())
    n = sum(n*(n-1) for n in data.values() if n != 0)
    if N-1 < 1:
        d = 0
    else:
        d = 1 - (float(n)/(N*(N-1)))
    return d

def calculateBiodiversity(in_feat):
    
    in_feat.dataProvider().addAttributes([QgsField("biod",QVariant.Double)])
    in_feat.updateFields()
    
    with edit(in_feat):
        for feat in in_feat.getFeatures():
            sim_di = simpson_di({'a':int(feat['STEMCOUNTPINE']),'b':int(feat['STEMCOUNTSPRUCE']),'c':int(feat['STEMCOUNTDECIDUOUS'])})
            if feat['SPECIALFEATURECODE'] is not None:
                conver_cof = sim_di * 0.1
            else:
                conver_cof = 0
            
            feat['biod'] = float(sim_di+conver_cof)
            in_feat.updateFeature(feat)
    
    normalizeValue(in_feat,'biod')

    
def normalizeValue(in_feat,fieldname):
    in_feat.dataProvider().addAttributes([QgsField(fieldname+"n",QVariant.Double)])
    in_feat.updateFields()
    lis = [feat[fieldname] for feat in in_feat.getFeatures() if feat[fieldname] is not None]
    try:
        minlis = min(lis)
        maxlis = max(lis)
    except:
        minlis = 0
        maxlis = 1

    with edit(in_feat):
        for feat in in_feat.getFeatures():
            if feat[fieldname] is not None:
                feat[fieldname+"n"] = (feat[fieldname]-minlis) / (maxlis-minlis)
            else:
                feat[fieldname+"n"] = 0.0
            
            in_feat.updateFeature(feat)

def calculateEnvValue(in_feat,weights):
    in_feat.dataProvider().addAttributes([QgsField("env_value",QVariant.Double)])
    in_feat.updateFields()

    with edit(in_feat):
        for feat in in_feat.getFeatures():
            feat['env_value'] = feat['biodn']*weights['BIO']+feat['pRetentn']*weights['NP']+feat['DTW_1n']*weights['DTW']+feat['dtreen']*weights['LP']
    
            in_feat.updateFeature(feat)

def hsAnalysis(in_feat,fieldname):
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
    
    return out

def optimizeRetentioTrees(in_feat,leimArea,treec):
    in_feat.dataProvider().addAttributes([QgsField("reTree",QVariant.Int)])
    in_feat.updateFields()

    #Rajataan leimikkoon ja poistetaan suojelualueet
    NoLeim = [feat.id() for feat in in_feat.getFeatures() if feat['leimikko']!=1 or feat['OBJECTID'] is not None or feat['SPECIALFEATUREADDITIONALCODE']== 43]
    in_feat.dataProvider().deleteFeatures(NoLeim)
    in_feat.updateFields()

    #if in_feat.featureCount()==0:
    
    #normalizeValue(in_feat,'HS_1')
    opt = np.array([feat['HS_1'] for feat in in_feat.getFeatures()])

    #kopioidaan taso
    #in_feat.selectAll()
    #clone = processing.run("native:saveselectedfeatures",{'INPUT':in_feat,'OUTPUT':'TEMPORARY_OUTPUT'})
    #clone = clone['OUTPUT']
    #in_feat.removeSelection()

    #rajataan
    #OPT = np.array([i[0] for i in arcpy.da.SearchCursor(temp,['OPT_value_HS'][0])])

    treecount = int(round(float(treec) * float(leimArea),0))
    pvalue = opt[np.argsort(opt)[-treecount]]
    #arcpy.CopyFeatures_management(temp,in_feat)
    
    with edit(in_feat):
        for feat in in_feat.getFeatures():
            if feat['HS_1']>=pvalue:
                feat['reTree']=1
            else:
                feat['reTree']=0
            in_feat.updateFeature(feat)
    
    return in_feat
    #noReTree = [feat.id() for feat in in_feat.getFeatures() if feat['HS_1']<pvalue]
    #clone.dataProvider().deleteFeatures(noReTree)

    #return clone
def cleanResults(puukartta: QgsVectorLayer):
    handle = puukartta.clone()

    NoReten = [feat.id() for feat in handle.getFeatures() if feat['reTree']==0]
    handle.dataProvider().deleteFeatures(NoReten)
    handle.updateFields()
    
    """ 1: delaunay kolmiointi 2: valitse jossa extent xmax - xmin ja ymax - ymin > 20 3: dissolve geometria 4: moniosaiset yksiosaisksi (5: laske keskiarvot)"""

    """ 
    conc = processing.run("qgis:concavehull", 
            {'INPUT':handle,'ALPHA':0.2,'HOLES':False,'NO_MULTIGEOMETRY':False,'OUTPUT':'TEMPORARY_OUTPUT'})
            
    buf = processing.run("native:buffer", {'INPUT':handle,'DISTANCE':2,'SEGMENTS':5,'END_CAP_STYLE':0,'JOIN_STYLE':0,'MITER_LIMIT':2,'DISSOLVE':False,'OUTPUT':'TEMPORARY_OUTPUT'})
    """

    #merge

def makeRetentionGraph(puukartta,graafi):
    if graafi == "":
        graafi = tempfile.TemporaryFile()
        graafi = graafi.name+'ymparistotekijat.png'
    
    #graafi_f = os.getcwd()
    #graafi = os.path.join(graafi_f,'ymparistotekijat.png')
    #print (graafi)
    #columns = ['dtree','BIOD','N_reten','DTW']
    collabels = ["Lahopuupotentiaali","Simpsonin biodiversiteetti-indeksi","Fosforin pidätys","Maaperän kosteus (DTW)"]

    puukartta_values = np.array([(i['dtreen'],i['biodn'],i['pRetentn'],i['DTW_1n']) for i in puukartta.getFeatures() if int(i['reTree']!=1)])
    saastopuu_values = np.array([[i['dtreen'],i['biodn'],i['pRetentn'],i['DTW_1n']] for i in puukartta.getFeatures() if int(i['reTree']==1)])

    puukartta_values = np.where(puukartta_values>=0,puukartta_values,np.nan)
    saastopuu_values = np.where(saastopuu_values>=0,saastopuu_values,np.nan)


    #data = [puukartta_values,saastopuu_values]
    fig, axs = plt.subplots(nrows=2, ncols=2, sharey=True)
    colors=['green','darkgreen','blue','darkblue']
    labels=["Leimikko","Säästopuut"]
    whiskerprops = dict(color='black')
    calc = 0
    for i in range(2):
        for j in range(2):
            boxprops = dict(color=colors[calc],linewidth=1.5)
            axs[i,j].boxplot(
                x=[puukartta_values[:,calc],saastopuu_values[:,calc]],\
                labels = labels,\
                boxprops = boxprops,\
                meanline = True,\
                whiskerprops = whiskerprops,\
                whis=(5,95),\
                showfliers=False)
            axs[i,j].set_title(collabels[calc],fontsize=12)
            axs[i,j].set_ylim(-0.1,1.1)
            calc+=1


    fig.suptitle('Ympäristötekijät hakkuulla',fontsize=14)
    fig.subplots_adjust(hspace=0.7)
    fig.savefig(graafi, dpi=150)
    return graafi

#testitaso = "S:/Luontotieto/QGIS_plugin_test/testitasot.gpkg|layername=tulostaso11"
#testitaso = QgsVectorLayer(testitaso,"testitaso","ogr")
#t = makeRetentionGraph(testitaso,"")
#print (t)
