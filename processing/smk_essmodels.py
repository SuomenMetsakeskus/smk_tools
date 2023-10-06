from qgis.core import QgsVectorLayer,QgsField,edit
from qgis.PyQt.QtCore import QVariant
from paras_2 import decay_tree_potential,NP_retention
from smk_geotools import hsAnalysis
import numpy as np

def limit(x,minimum,maximum):
    """
    This adjust given value to minimum or maximum if outsite of the scale
    """
    if type(x)==float or type(x) == int:
        fc = lambda x : x if x>minimum and x<maximum else (minimum if x<=minimum else maximum)
    else:
        fc = lambda x : x
    l = fc(x)
    return l

def normalizeValue(in_feat:QgsVectorLayer,fieldname:str,filtervalues:tuple,transpose:bool=False):
    """
    This normalize values between 0 and 1 by formula f(x) = x-min(x) / max(x) - min(x)
    You can limit values between specific values and transpose the values
    """
    in_feat.dataProvider().addAttributes([QgsField(fieldname+"n",QVariant.Double)])
    in_feat.updateFields()
    
    lis = [feat[fieldname] for feat in in_feat.getFeatures() if feat[fieldname] is not None]
    
    #print (lis)
    if filtervalues is not None:
        lis = [limit(i,filtervalues[0],filtervalues[1]) for i in lis]
        with edit(in_feat):
            for feat in in_feat.getFeatures():
                feat[fieldname]=limit(feat[fieldname],filtervalues[0],filtervalues[1])
                in_feat.updateFeature(feat)
                
    try:
        minlis = min(list(lis))
        maxlis = max(list(lis))
        
    except:
        minlis = 0
        maxlis = 1
    
    
    with edit(in_feat):
        for feat in in_feat.getFeatures():
            if type(feat[fieldname]) in (int,float):
                if transpose == False:
                    feat[fieldname+"n"] = (feat[fieldname]-minlis) / (maxlis-minlis)
                else:
                    feat[fieldname+"n"] = 1- ((feat[fieldname]-minlis) / (maxlis-minlis))
            else:
                feat[fieldname+"n"] = 0.0
            
            in_feat.updateFeature(feat)

def simpson_di(species):
    """
    This calculates simpson diversity index by formula D = n(n-1)/N(N-1)
    Species list are form of [10,1,3,4]
    """
    
    proportions = [i/sum(species) for i in species]
    simpsons_index = 0
    for proportion in proportions:
        simpsons_index += proportion ** 2
    
    return (1 - simpsons_index) / (1-1/len(species)) if simpsons_index > 0 and len(species)>1 else 0

def calculateBiodiversity(in_feat:QgsVectorLayer,speciesfield:list):
    """
    This calculates specific diversity index by given species list and save it to given QgsVectorLayer.
    Species list have to be format of [1,35,42,2,23,...,n]
    """
    
    in_feat.dataProvider().addAttributes([QgsField("biod",QVariant.Double)])
    in_feat.updateFields()
    
    with edit(in_feat):
        for feat in in_feat.getFeatures():
            
            sim_di = simpson_di([feat[i] for i in speciesfield if type(feat[i]) in (int,float)])
            
            feat['biod'] = float(sim_di)
            in_feat.updateFeature(feat)
    
    normalizeValue(in_feat,'biod',None,False)

def calculateDecayTreePotential(in_feat,fz_field):
    
    in_feat.dataProvider().addAttributes([QgsField("dtree",QVariant.Double)])
    in_feat.updateFields()
    
    #treelist = [1,2,29]
    puuH = [("MEANHEIGHTPINE",1),("MEANHEIGHTSPRUCE",2),("MEANHEIGHTDECIDUOUS",29)]
    fc_d = lambda t : t.replace("HEIGHT","DIAMETER")
    fc_v = lambda t : t.replace("HEIGHT","VOLUME")
    
    with edit(in_feat):
        for feat in in_feat.getFeatures():
            if type(feat[fz_field]) in (str,int,float):
                dcp = decay_tree_potential('zone'+str(feat[fz_field]))
            else:
                dcp = decay_tree_potential('zone3')
            if type(feat['FERTILITYCLASS']) in (float,int) and max([feat[p[0]] for p in puuH]) >0:
                if feat['FERTILITYCLASS']>6:
                    para = [dcp[6][i[1]] for i in puuH]
                else:
                    para = [dcp[int(feat['FERTILITYCLASS'])][i[1]] for i in puuH]
                                    
                potvalues = [limit(np.poly1d(para[i])(feat[fc_d(p[0])]),0,2) for i,p in enumerate(puuH) if feat[fc_d(p[0])] > 0]
            
            else:
                potvalues=[0]
            
            feat["dtree"]=float(sum(potvalues))
            
            
            in_feat.updateFeature(feat)
    
    normalizeValue(in_feat,"dtree",None,False)

def calculateNPretention(in_feat):
    in_feat.dataProvider().addAttributes([QgsField("pRetent",QVariant.Double)])
    in_feat.updateFields()
    ret = NP_retention()
    with edit(in_feat):
        for feat in in_feat.getFeatures():
            if type(feat['euc_1']) in (float,int):
                feat['pRetent'] = ret['P']/limit(feat['euc_1'],1,40) * feat['DTW_1n']
                
            in_feat.updateFeature(feat)
    
    normalizeValue(in_feat,'pRetent',None,False)

def calculateEnvValue(in_feat,weights):
    in_feat.dataProvider().addAttributes([QgsField("env_value",QVariant.Double)])
    in_feat.updateFields()

    with edit(in_feat):
        for feat in in_feat.getFeatures():
            feat['env_value'] = feat['biodn']*weights['BIO']+feat['pRetentn']*weights['NP']+feat['DTW_1n']*weights['DTW']+feat['dtreen']*weights['LP']
            
            #normalizeValue(in_feat,'env_value',None,False)
            in_feat.updateFeature(feat)

def selectReTrees(in_feat:QgsVectorLayer,fieldname:str,cuttingfield:str,treecount:int,cuttingsize:float):
    """
    This select retention trees by given QgsVectorLayer, fieldname and treecount. Parameter "cuttingfield" restrict selection to cutting area 
    """
    
    in_feat.dataProvider().addAttributes([QgsField("reTree",QVariant.Int)])
    in_feat.updateFields()

    #Restrict to cutting area
    NoLeim = [feat.id() for feat in in_feat.getFeatures() if feat[cuttingfield]!=1]
    in_feat.dataProvider().deleteFeatures(NoLeim)
    in_feat.updateFields()

    #getting to values in which we do the selection
    opt = np.array([feat[fieldname] for feat in in_feat.getFeatures()])

    treecount = int(round(float(treecount) * float(cuttingsize),0))
    pvalue = opt[np.argsort(opt)[-treecount]]
    
    
    with edit(in_feat):
        for feat in in_feat.getFeatures():
            if feat[fieldname]>=pvalue:
                feat['reTree']=1
            else:
                feat['reTree']=0
            in_feat.updateFeature(feat)

def runEssModel(in_feat:QgsVectorLayer,weights,treecount,cuttingsize,fz_field):
    normalizeValue(in_feat,"DTW_1",(0.0,0.8),True)
    calculateBiodiversity(in_feat,["STEMCOUNTPINE","STEMCOUNTDECIDUOUS","STEMCOUNTSPRUCE"])
    calculateDecayTreePotential(in_feat,fz_field)
    calculateNPretention(in_feat)
    calculateEnvValue(in_feat,weights)
    retrees = hsAnalysis(in_feat,'env_value')
    selectReTrees(retrees,'HS_1','leimikko',treecount,cuttingsize)

    return retrees
