# -*- coding: utf-8 -*-

__author__ = 'Suomen metsäkeskus'
__date__ = '2022-10-04'
__copyright__ = '(C) 2022 by Suomen metsäkeskus'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'
from stat import S_ISLNK


import os,sys
from qgis import processing
import pandas as pd
from qgis.utils import iface
from osgeo import gdal,gdal_array
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterPoint,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterVectorDestination,
                       QgsVectorLayer,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingUtils,
                       QgsProcessingParameterDefinition,
                       QgsProcessingMultiStepFeedback,
                       QgsProcessingFeatureSourceDefinition,
                       QgsFeatureRequest,
                       QgsRasterLayer)

sys.path.append(os.path.dirname(__file__))
from .smkluoto_geotools import *


class Valumamalli_fi(QgsProcessingAlgorithm):
    jako5 = QgsVectorLayer("crs='EPSG:3067' url='https://aineistot.metsakeskus.fi/metsakeskus/rest/services/Luontotieto/Valumaalueet_t5/MapServer/0' http-header:referer=''","jako5","arcgisfeatureserver")
    DEMurl = "cache=PreferNetwork&dpiMode=7&format=GeoTIFF&identifier=1&url=https://aineistot.metsakeskus.fi/metsakeskus/services/Vesiensuojelu/DEM/ImageServer/WCSServer"
    D8url = "cache=PreferNetwork&dpiMode=7&format=GeoTIFF&identifier=1&url=https://aineistot.metsakeskus.fi/metsakeskus/services/Vesiensuojelu/D8_suomi/ImageServer/WCSServer"
    FAurl = "cache=PreferNetwork&dpiMode=7&format=GeoTIFF&identifier=1&url=https://aineistot.metsakeskus.fi/metsakeskus/services/Vesiensuojelu/Virtausverkko/MapServer/WCSServer"

    #jako5 = iface.addVectorLayer(jako5l)
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterNumber('tartunta', 'Tartuntaetäisyys', type=QgsProcessingParameterNumber.Integer, minValue=0, maxValue=20, defaultValue=5))
        self.addParameter(QgsProcessingParameterPoint('purkupiste', 'purkupiste', defaultValue='0.000000,0.000000'))
        self.addParameter(QgsProcessingParameterFeatureSink('Valuma-alue', 'Valuma-alue'))
        #params = []
        #params.append(QgsProcessingParameterRasterLayer("d8","suuntarasteri",defaultValue="suuntarasteri"))
        #params.append(QgsProcessingParameterRasterLayer("fa","virtausverkko",defaultValue="virtausverkko"))
        #[p.setFlags(p.flags | QgsProcessingParameterDefinition.FlagAdvanced) for p in params]
        #for p in params:
         #   p.setFlags(p.flags() | QgsProcessingParameterDefinition.FlagAdvanced) 
          #  self.addParameter(p)
        #self.addParameter(QgsProcessingParameterRasterDestination('Outrast', 'outrast', createByDefault=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(6, model_feedback)
        results = {}
        outputs = {}
        try:
            # Luo taso pisteestä
            alg_params = {
                'INPUT': parameters['purkupiste'],
                'OUTPUT': "TEMPORARY_OUTPUT"
            }
            outputs['LuoTasoPisteest'] = processing.run('native:pointtolayer', alg_params, context=context, feedback=feedback, is_child_algorithm=False)

            feedback.setCurrentStep(1)
            if feedback.isCanceled():
                return {}
            
            
            jako5_raj = processing.run("native:joinattributesbylocation",
                            {'INPUT':self.jako5,
                                'PREDICATE':[0],
                                'JOIN':outputs['LuoTasoPisteest']['OUTPUT'],
                                'JOIN_FIELDS':[],
                                'METHOD':1,
                                'DISCARD_NONMATCHING':True,
                                'PREFIX':'',
                                'OUTPUT':'TEMPORARY_OUTPUT'},context=context, feedback=feedback, is_child_algorithm=False)

            jako5_raj = jako5_raj['OUTPUT']
            #feedback.pushInfo("jotain: "+jako5_raj)
            #feedback.pushInfo("coords = %f,%f,%f,%f" %(jako5_raj.extent().xMinimum(), jako5_raj.extent().xMaximum(), jako5_raj.extent().yMinimum(), jako5_raj.extent().yMaximum()))
            feedback.setCurrentStep(2)
            if feedback.isCanceled():
                return {}
            
            jako5_raj = processing.run("native:buffer",
                            {'INPUT':jako5_raj,
                                'DISTANCE':500,
                                'SEGMENTS':5,
                                'END_CAP_STYLE':0,
                                'JOIN_STYLE':0,
                                'MITER_LIMIT':2,
                                'DISSOLVE':True,
                                'OUTPUT':'TEMPORARY_OUTPUT'},context=context, feedback=feedback,is_child_algorithm=False)
            
            #results['Valuma'] = parameters['Valuma']

            jako5_raj = jako5_raj['OUTPUT']
            jako5_raj.updateExtents()
            
            #feedback.pushInfo(str(jako5_raj.extent()))
            feedback.setCurrentStep(3)
            if feedback.isCanceled():
                return {}
            
            feedback.setProgressText("rajataan tausta-aineistot valuma-alueelle")
            #layer = QgsProcessingUtils.mapLayerFromString(jako5_raj, context)
            #D8 = QgsProcessingUtils.mapLayerFromString(parameters['d8'],context)
            D8 = QgsRasterLayer(self.D8url,"suuntarasteri","wcs")
            D8= clipRaster3(D8,jako5_raj)
            FA = QgsRasterLayer(self.FAurl,"virtasverkko","wcs")
            #FA = QgsProcessingUtils.mapLayerFromString(parameters['fa'],context)
            FA= clipRaster3(FA,jako5_raj)
            FA = QgsRasterLayer(FA,"flowaccu","gdal")
            
            feedback.setProgressText("")
            d8_raj = processing.run("grass7:r.reclass",
                            {'input':D8,
                            'rules':'',
                            'txtrules':'1=8\n2=7\n4=6\n8=5\n16=4\n32=3\n64=2\n128=1\n',
                            'output':QgsProcessing.TEMPORARY_OUTPUT,
                            'GRASS_REGION_PARAMETER':'',
                            'GRASS_REGION_CELLSIZE_PARAMETER':0,
                            'GRASS_RASTER_FORMAT_OPT':'',
                            'GRASS_RASTER_FORMAT_META':''},context=context, feedback=feedback)
            
            feedback.setCurrentStep(4)
            if feedback.isCanceled():
                return {}
            """
            snap = processing.run("saga:snappointstoraster",
                        {'INPUT':outputs['LuoTasoPisteest']['OUTPUT'],
                        'GRID':FA,
                        'OUTPUT':QgsProcessing.TEMPORARY_OUTPUT,
                        'MOVES':QgsProcessing.TEMPORARY_OUTPUT,
                        'DISTANCE':parameters['tartunta'],
                        'SHAPE':0,
                        'EXTREME':1},context=context, feedback=feedback,is_child_algorithm=False)"""
            
            snap = snappoint2raster(outputs['LuoTasoPisteest']['OUTPUT'],FA,parameters['tartunta'])
            #snap = QgsVectorLayer(snap['OUTPUT'],"snap","ogr")
            feedback.pushInfo(str(snap.featureCount()))
            feedback.setCurrentStep(5)
            if feedback.isCanceled():
                return {}
            
            snapfeat = next(snap.getFeatures())
            srid=str(snap.crs().authid())
            geom = str(snapfeat.geometry().asPoint().x())+","+str(snapfeat.geometry().asPoint().y())+" ["+srid+"]"

            basin = processing.run("grass7:r.water.outlet",
                        {'input':d8_raj['output'],
                            'coordinates':geom,
                            'output':QgsProcessing.TEMPORARY_OUTPUT,
                            'GRASS_REGION_PARAMETER':None,
                            'GRASS_REGION_CELLSIZE_PARAMETER':0,
                            'GRASS_RASTER_FORMAT_OPT':'',
                            'GRASS_RASTER_FORMAT_META':''},context=context, feedback=feedback)
            
            feedback.setCurrentStep(6)
            if feedback.isCanceled():
                return {}
            
            dataset = {'pinta_ala':30.1}
            df = pd.DataFrame(dataset,index=[0])
            out = raster2vector2(basin["output"],df)
        except Exception as e:
            feedback.pushWarning(e)
        style = os.path.join(os.path.dirname(__file__),"valumaalue_style.qml")
        #feedback.pushInfo(str(style))
        #layer = QgsVectorLayer(vect.source(),'Valuma-alue','ogr')
        
        #outputs['Valuma'] = processing.run("saga:copyfeatures", {'SHAPES':vect.source(),'COPY':parameters['Valuma']},context=context, feedback=feedback,is_child_algorithm=True)
        #outputs['Valuma']['COPY']
        #out = QgsVectorLayer(outputs['Valuma']['COPY'],"Valuma","ogr")
        #outputs['style'] = processing.run("native:setlayerstyle", {'INPUT':outputs['Valuma']['COPY'],'STYLE':style},context=context, feedback=feedback, is_child_algorithm=True)
        (sink, dest_id) = self.parameterAsSink(parameters,'Valuma-alue',context,
                    out.fields(), out.wkbType(), out.crs())
            #feedback.pushInfo(str(out.fields().names()))
        outFeats = out.getFeatures()
        for outFeat in outFeats:
            #feedback.pushInfo(str(outFeat['CHM']))
            sink.addFeature(outFeat, QgsFeatureSink.FastInsert)

        layer = QgsProcessingUtils.mapLayerFromString(dest_id, context)
        layer.loadNamedStyle(style)
        return {'Valuma-alue': dest_id}
    
    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Valuma-alueen määritys'


    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return 'Valuma-alueen määritys'

    def icon(self):
        
        return QIcon('planet.png')
    
    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return 'luoto'

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return ''


    def createInstance(self):
        return Valumamalli_fi()







