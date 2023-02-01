import os,sys,subprocess
import numpy as np
import pandas as pd
from osgeo import gdal,gdal_array
from qgis.PyQt.QtCore import QVariant
import tempfile,requests
from saastopuu import getBboxWmsFormat
from qgis.core import QgsVectorLayer,QgsField,QgsFeature,edit
import processing
import matplotlib.pyplot as plt
from math import sqrt
from whitebox.whitebox_tools import WhiteboxTools


#inp = r'S:/Luontotieto/QGIS_plugin_test/testitasot.gpkg|layername=suojakaistaLeim'
#inp = QgsVectorLayer(inp,"input","ogr")
#outr = 'S:/Luontotieto/QGIS_plugin_test/testirrr.tif'
#out = QgsRasterLayer(outr,"outrast")
pnimet = ['suojakaista_taustarasterit','RUSLE','MassataseGISSUS','WB_Finland','DEM'] #taustarastereissa band1 = costdistance ; band2 = euclidean ; band3 = lsn
wbt = WhiteboxTools()

def getWater(input_polygon,taso):
    tempd = tempfile.TemporaryFile()
    #os.makedirs(tempd.name)
    #tempd = tempd.name+'.tif'
    #tempd = os.path.dirname(os.path.realpath(tempd))
    
    tempd = tempd.name+str(taso)+'.tif'
    bbox = getBboxWmsFormat(input_polygon)
    #print (bbox)
    ss = bbox[0].split(',')

    wmsurl = 'https://aineistot.metsakeskus.fi/metsakeskus/rest/services/Vesiensuojelu/'+taso+'/ImageServer/exportImage?'
    params = {"bbox":str(round(int(ss[0])-100,-1))+","+str(round(int(ss[1])-100,-1))+","+str(round(int(ss[2])+100,-1))+","+str(round(int(ss[3])+100,-1)),
                "bboxSR":3067,
                "size":str((round(int(ss[2])+100,-1)-round(int(ss[0])-100,-1))/2)+","+str((round(int(ss[3])+100,-1) - round(int(ss[1])-100,-1))/2),
                "imageSR":3067,
                "format":'tiff',
                "pixelType":"F32",
                "noData":0,
                "noDataInterpretation":"esriNoDataMatchAny",
                "interpolation":"+RSP_BilinearInterpolation",
                "f":"image"}

    #print (params)
    #print (str(round(int(ss[0])-100,-1))+","+str(round(int(ss[1])-100,-1))+","+str(round(int(ss[2])+100,-1))+","+str(round(int(ss[3])+100,-1))+" ")
    test = requests.get(wmsurl,params,allow_redirects=True)
    respo = test.content
    open(tempd,"wb").write(respo)


    return tempd

def feature2layer(feature):
    vl = QgsVectorLayer("Polygon", "temporary_pol", "memory")
    pr = vl.dataProvider()
    # Enter editing mode
    vl.startEditing()
    pr.addAttributes( [QgsField("id",  QVariant.Int)])

    fet = QgsFeature()
    fet.setGeometry( feature.geometry())
    fet.setAttributes(feature.attributes())
    pr.addFeatures( [ fet ] )
    
    vl.commitChanges()

    return vl
    #fields = maplayer.fields()



def rasterizeVector(in_layer,cells):
    #print ("jee")
    tempd = tempfile.TemporaryFile()
    tempd = tempd.name+'.tif'

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
                        'OUTPUT':tempd})

    return tempd

def raster2Array(in_raster,band):
    
    rast = gdal.Open(in_raster)
    rastB = rast.GetRasterBand(band)
    rastA = rastB.ReadAsArray()

    return rastA


def avoidedMassflux(rusle,ls,zone):

    rusleA = raster2Array(rusle,1)
    rusleA = rusleA / 1000
    lsA = raster2Array(ls,3)
    lsA = lsA/100*rusleA
    #print(rusleA-lsA/100)
    #zoneA = raster2Array(zone,1)
    sum_rusle = np.where(zone==1,rusleA,0)
    sum_ls = np.where(zone==1,lsA,0)
    rus = np.sum(sum_rusle)
    amf = np.sum(sum_ls)

    return amf,rus

def loggingEffect(rusle,ls,zoneA,zoneB):

    logging = avoidedMassflux(rusle,ls,zoneA)
    #print (logging)
    bzone = avoidedMassflux(rusle,ls,zoneB)

    acc_max = logging[1] #accumulation max
    ret_max = logging[1] - logging[0] #retention max (accumalation max - natural accumulation)
    acc_nat = logging[0] #natural accumulation
    acc_bz = logging[1]-bzone[1]+bzone[0] #accumulation with buffer zone (accumulation max - accumulation max in buffer zone + accumulation in buffer zone)
    acc_res = logging[1]-(logging[1]-bzone[1]+bzone[0]) #reserved accumulation (accumulation max - accumulation with buffer zone)
    acc_add = ret_max - acc_res #added accumulation (retention max - reserved accumulation)
    eff_res = round(acc_res / ret_max * 100,1) #effect of reserved accumulation (%) (reserved accumulation / retention max * 100)
    
    #print (acc_max,ret_max,acc_nat,acc_bz,acc_res,acc_add,eff_res)
    return(acc_max,ret_max,acc_nat,acc_bz,acc_res,acc_add,eff_res)
    
    
    
def raster2vector(in_rast,data):
    
    vectn = processing.run("gdal:polygonize", 
        {'INPUT':in_rast,
        'BAND':1,
        'FIELD':'DN',
        'EIGHT_CONNECTEDNESS':False,
        'EXTRA':'',
        'OUTPUT':'TEMPORARY_OUTPUT'})
    
    vect = QgsVectorLayer(vectn['OUTPUT'],"vyohyke","ogr")
    
    namelist = list(data.columns)
    for i in namelist:
        vect.dataProvider().addAttributes([QgsField(i,QVariant.Double)])
        vect.updateFields()
    
    with edit(vect):
        for feat in vect.getFeatures():
            if feat['DN'] == 0:
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
    
def array2raster(in_array,map_raster):
    tempd = tempfile.TemporaryFile()
    tempd = tempd.name+'.tif'
    
    gdal_array.SaveArray(in_array.astype("float32"),tempd,"GTiff",map_raster)

    return tempd

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
    #huip = focal - chmA
    huip = np.where(focal-rastA==2,1,0)
    #huip = np.where(huip>=5,huip*10,np.NaN)
    print (huip)
    print (np.max(huip))
    gdal_array.SaveArray(huip.astype("float32"),rastOut,"GTiff",rast)
    #gdal.Open(rastOut).GetRasterBand(1).SetNoDataValue(-9999)
    
    return rastOut

def massfluxgraph(all):
    graafi = tempfile.TemporaryFile()
    graafi = graafi.name+'.png'

    plt.clf()
    plt.bar(all['area_ratio'],all['effect_bufferzone'])
    plt.xlabel("Area coverage (%)")
    plt.ylabel("Avoided massflux (%)")
    plt.savefig(graafi, dpi=150)
    
    return graafi

def clipRaster(in_raster,clip_raster):

    output = tempfile.TemporaryFile()
    output = output.name+'.tif'    
    
    in_arr = raster2Array(in_raster,1)
    cl_arr = raster2Array(clip_raster,1)
    
    in_arr = np.where(cl_arr>0,in_arr,0)
    
    gdal_array.SaveArray(in_arr.astype("float32"),output,"GTiff",in_raster)
    
    return output

def my_callback(value):
    if not "%" in value:
        print(value)

def wbtBreachDepression(dem):
    #wbt = WhiteboxTools()
    output = os.path.dirname(os.path.realpath(dem))
    output = os.path.join(output,"dem_br.tif")
    
    wbt.breach_depressions(
        dem,
        output,
        max_depth=None,
        max_length=None,
        flat_increment=None,
        fill_pits=False,
        callback=my_callback
    )
    
    return output

def wbtD8Pointer(dem):
    output = os.path.dirname(os.path.realpath(dem))
    output = os.path.join(output,"d8.tif")  
    
    wbt.d8_pointer(
        dem, 
        output,
        esri_pntr = True,
        callback=my_callback
        )
    
    return output

def wbtWatershed(d8,pour_pts):
    output = os.path.dirname(os.path.realpath(d8))
    output = os.path.join(output,"watshed.tif")    
    wbt.watershed(
        d8, 
        pour_pts, 
        output, 
        esri_pntr=True, 
        callback=my_callback
    )
    return output

def bufferzone(logging,rasters,target):
    zraster = raster2Array(rasters[0],1)
    lraster = rasterizeVector(logging,2)
    
    wline = processRaster(rasters[3])
    lrast_clip = clipRaster(wline,lraster)

    lraster = raster2Array(lraster,1)
    print (rasters[4])
    dem_bd = wbtBreachDepression(rasters[4])
    d8 = wbtD8Pointer(dem_bd)
    waters = wbtWatershed(d8,lrast_clip)

    wshed_arr = raster2Array(waters,1)
    #wshed_arr = np.where((wshed_arr>0) or (r))
    lzone = np.where((zraster!=0) & (lraster!=0) & (wshed_arr>0),lraster,0)

    
    d1=[]
    arl =[]
    t = 0
    for i in range(0,105,5):
        zzone = np.where(lraster==1,zraster,0)
        z = zzone[zzone > 0]
        z = np.percentile(z,i)
        
        zzone = np.where((zzone<z) & (zzone != 0),1,0)
        
        effect = loggingEffect(rasters[1],rasters[0],lraster,zzone)
        ar = round(float((np.sum(zzone) / np.sum(lzone) * 100)),1)
        d1.append(effect)
        arl.append(ar)
        print (target)
        
        if effect[6] > target and t == 0:
            t = 1
            effect_c = effect
            ar_c = ar
            zzone_c = zzone
        #print (z,effect[3])
    
    #print (d1)
    bzone = array2raster(zzone_c,rasters[1])
    
    dataset = {'massflux_max':[effect_c[0]],
                'retention_max':[effect_c[1]],
                'natural_massflux':[effect_c[2]],
                'massflux_bufferzone':[effect_c[3]],
                'massflux_reserved':[effect_c[4]],
                'massflux_added':[effect_c[5]],
                'effect_bufferzone':[effect_c[6]],
                'area_ratio':ar_c}

    dataset_all = {'massflux_max':[i[0] for i in d1],
                'retention_max':[i[1] for i in d1],
                'natural_massflux':[i[2] for i in d1],
                'massflux_bufferzone':[i[3] for i in d1],
                'massflux_reserved':[i[4] for i in d1],
                'massflux_added':[i[5] for i in d1],
                'effect_bufferzone':[i[6] for i in d1],
                'area_ratio':arl}

    df = pd.DataFrame(dataset)
    df_all = pd.DataFrame(dataset_all)

    fig = massfluxgraph(df_all)
    #data_object = json.dumps(str(dataset_all),indent=8)
    #with open(r'C:\GitRepo\Luontotieto\QGIS\smk_tools\processing\testdata.json','w') as f:
    #    f.write(data_object)
    res = raster2vector(bzone,df)

    return res,fig

"""
rasterit = []
for i in pnimet:
    #print (i)
    rast = getWater(inp,i)
    #rast = gdal.Open(rast)
    rasterit.append(rast)
    #exit

out = [inp]
#rasterizeVector(inp,2,outr)
#print (rasterit)
#avoidedMassflux(rasterit[1],rasterit[0],outr)
test = bufferzone(inp,rasterit,50)



iface.addVectorLayer(test,"testileimi","ogr")
"""