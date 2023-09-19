import os,sys
import processing
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
                       QgsProcessingParameterVectorDestination,
                       QgsVectorLayer,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingUtils,
                       QgsProcessingParameterDefinition,
                       QgsProcessingMultiStepFeedback,
                       QgsProcessingFeatureSourceDefinition,
                       QgsFeatureRequest)

from getInput import getBboxWmsFormat
from getInput import getWater
from fcFunctions import raster2vector2

pluginPath = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        os.pardir))

class Valumamalli(QgsProcessingAlgorithm):
    jako5 = QgsVectorLayer("crs='EPSG:3067' crs='EPSG:3067' url='https://aineistot.metsakeskus.fi/metsakeskus/rest/services/Luontotieto/Valumaalueet_t5/MapServer/0'","jako5","arcgisfeatureserver")
    #jako5 = iface.addVectorLayer(jako5l)
    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterNumber('tartunta', 'Tartuntaetäisyys', type=QgsProcessingParameterNumber.Integer, minValue=0, maxValue=20, defaultValue=5))
        self.addParameter(QgsProcessingParameterPoint('tt', 'purkupiste', defaultValue='0.000000,0.000000'))
        self.addParameter(QgsProcessingParameterVectorDestination('Valuma', 'Valuma',type=QgsProcessing.TypeVectorAnyGeometry,createByDefault=True, defaultValue=None))
        #self.addParameter(QgsProcessingParameterRasterDestination('Outrast', 'outrast', createByDefault=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(6, model_feedback)
        results = {}
        outputs = {}

        # Luo taso pisteestä
        alg_params = {
            'INPUT': parameters['tt'],
            'OUTPUT': "TEMPORARY_OUTPUT"
        }
        outputs['LuoTasoPisteest'] = processing.run('native:pointtolayer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

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
                            'OUTPUT':QgsProcessing.TEMPORARY_OUTPUT},context=context, feedback=feedback, is_child_algorithm=True)

        jako5_raj = jako5_raj['OUTPUT']
        

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
                            'OUTPUT':QgsProcessing.TEMPORARY_OUTPUT},context=context, feedback=feedback)
        
        #results['Valuma'] = parameters['Valuma']

        jako5_raj = jako5_raj['OUTPUT']
        #jako5_raj.updateExtents()

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}
        
        DEM = getWater(jako5_raj,"DEM")
        feedback.pushInfo(DEM[1])
        D8= getWater(jako5_raj,"D8_suomi")
        feedback.pushInfo(D8[1])

        d8_raj = processing.run("grass7:r.reclass",
                        {'input':D8[0],
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

        snap = processing.run("saga:snappointstoraster",
                      {'INPUT':outputs['LuoTasoPisteest']['OUTPUT'],
                       'GRID':DEM[0],
                       'OUTPUT':QgsProcessing.TEMPORARY_OUTPUT,
                       'MOVES':QgsProcessing.TEMPORARY_OUTPUT,
                       'DISTANCE':parameters['tartunta'],
                       'SHAPE':0,
                       'EXTREME':0},context=context, feedback=feedback)
        
        snap = QgsVectorLayer(snap['OUTPUT'],"snap","ogr")
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
        vect = raster2vector2(basin["output"],df)
        
        style = os.path.join(os.path.dirname(__file__),"valumaalue_style.qml")
        feedback.pushInfo(str(style))
        #layer = QgsVectorLayer(vect.source(),'Valuma-alue','ogr')
        
        outputs['Valuma'] = processing.run("saga:copyfeatures", {'SHAPES':vect.source(),'COPY':parameters['Valuma']},context=context, feedback=feedback,is_child_algorithm=True)
        #outputs['Valuma']['COPY']
        results['Valuma'] = outputs['Valuma']['COPY']
        outputs['style'] = processing.run("native:setlayerstyle", {'INPUT':outputs['Valuma']['COPY'],'STYLE':style},context=context, feedback=feedback, is_child_algorithm=True)
        
        return results
    
    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Luo valuma-alue'

    def icon(self):
        
        return QIcon(os.path.join(pluginPath, 'icon.jpg'))

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr(self.name())

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr(self.groupId())

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'SMK luontotieto'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return Valumamalli()







