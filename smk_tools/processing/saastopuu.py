# -*- coding: utf-8 -*-
from base64 import decode
from osgeo import gdal,gdal_array
import pandas as pd
import numpy as np
from math import sqrt,pow
from qgis.PyQt.QtCore import QVariant
from paras_2 import decay_tree_potential,NP_retention
import matplotlib.pyplot as plt
from qgis import processing
from qgis.analysis import QgsInterpolator,QgsIDWInterpolator,QgsGridFileWriter
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsVectorLayer,edit)
import os,tempfile

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
        



def calculateNPretention(in_feat):
    in_feat.dataProvider().addAttributes([QgsField("pRetent",QVariant.Double)])
    in_feat.updateFields()
    ret = NP_retention()
    with edit(in_feat):
        for feat in in_feat.getFeatures():
            if type(feat['euc_1']) in (float,int):
                feat['pRetent'] = ret['P']/feat['euc_1']
                
            in_feat.updateFeature(feat)
    
    normalizeValue(in_feat,'pRetent')


def simpson_di(data):
    N = sum(n for n  in data.values() if type(n) == int or type(n) == float)
    n = sum(n*(n-1) for n in data.values() if type(n) == int or type(n) == float)
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
            sim_di = simpson_di({'a':feat['STEMCOUNTPINE'],'b':feat['STEMCOUNTSPRUCE'],'c':feat['STEMCOUNTDECIDUOUS']})
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
