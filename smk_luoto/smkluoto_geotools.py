from qgis.core import QgsRectangle,QgsRasterLayer,QgsRasterPipe,QgsRasterProjector,QgsRasterFileWriter,QgsVectorLayer,edit,QgsPointXY,QgsGeometry,QgsRaster,QgsField
from qgis import processing
from qgis.PyQt.QtCore import QVariant
from shapely.geometry import Point
from qgis.analysis import QgsGridFileWriter
import tempfile

#processing
#QgsVectorLayer,edit

def clipRaster3(rlayer,mask_layer):
    renderer = rlayer.renderer()
    provider = rlayer.dataProvider()
    crs = rlayer.crs()

    pipe = QgsRasterPipe()
    projector = QgsRasterProjector()
    projector.setCrs(provider.crs(), provider.crs())

    if not pipe.set(provider.clone()):
        print("Cannot set pipe provider")

    # Commented for extract raw data
    # if not pipe.set(renderer.clone()):
        # print("Cannot set pipe renderer")

    if not pipe.insert(2, projector):
        print("Cannot set pipe projector")

    
    out_file = tempfile.TemporaryFile()
    out_file = out_file.name+'.tif'
    #out_file = 'D:/temp/temporal.tif'
    file_writer = QgsRasterFileWriter(out_file)
    file_writer.Mode(1)

    print ("Saving")

    extent = mask_layer.extent()

    opts = ["COMPRESS=LZW"]
    file_writer.setCreateOptions(opts)
    error = file_writer.writeRaster(
        pipe,
        extent.width (),
        extent.height(),
        extent,
        crs)

    if error == QgsRasterFileWriter.NoError:
        print ("Raster was saved successfully!")
        #layer = QgsRasterLayer(out_file, "result")
        
    else:
        print ("Raster was not saved!")

    return out_file
    

def raster2vector2(in_rast,data):
    """transfrom input buffer zone raster to vector"""
    vectn = processing.run("gdal:polygonize", 
        {'INPUT':in_rast,
        'BAND':1,
        'FIELD':'DN',
        'EIGHT_CONNECTEDNESS':False,
        'EXTRA':'',
        'OUTPUT':'TEMPORARY_OUTPUT'})
    
    vect = QgsVectorLayer(vectn['OUTPUT'],"vyohyke","ogr")
    #arealist = [feat.geometry().area() for feat in vect.getFeatures() if feat['DN']==1]
    namelist = list(data.columns)
    for i in namelist:
        vect.dataProvider().addAttributes([QgsField(i,QVariant.Double)])
        vect.updateFields()
    
    #ids = [(i.id(),i) for i in vect.getFeatures()]
    #fs = [i for i in]
    geom = [i.geometry().buffer(15,5) for i in vect.getFeatures()]
    g=geom[0]
    for i in geom:
        geo = i.combine(g)
         
    c = 0
    with edit(vect):
        for feat in vect.getFeatures():
            if c == 0:

                for i in namelist:
                    datac = data[[i]]
                    print (datac.iloc[0,0])
                    feat[i] = float(datac.iloc[0,0])
            
                #geom = feat.geometry()
                #buffer = geom.buffer(15, 5)
                buffer = geo.buffer(-14,5)
                feat.setGeometry(buffer)
                feat['pinta_ala'] = round(buffer.area()/10000,2)
                vect.updateFeature(feat)
                c = 1
            else:
                vect.deleteFeature(feat.id())
            vect.updateFeature(feat)
    return vect

def snappoint2raster(point_layer,raster_layer,radius):
    #define output
    output_layer = QgsVectorLayer("Point?crs=epsg:3067", "output", "memory")
    output_provider = output_layer.dataProvider()
    output_fields = point_layer.fields()
    output_provider.addAttributes(output_fields)
    output_layer.updateFields()


    for feature in point_layer.getFeatures():
        point = feature.geometry().asPoint()
        circular_area = Point(point).buffer(radius)
        max_value = -float('inf')
        max_point = None
        
        # Loop through the raster cells within the circular area
        for cell in circular_area.exterior.coords:
            #print (cell)
            value = raster_layer.dataProvider().identify(QgsPointXY(cell[0],cell[1]), QgsRaster.IdentifyFormatValue).results()[1]
            if value is not None and value > max_value:
                max_value = value
                max_point = QgsPointXY(cell[0],cell[1])
        
        # Snap the vector point to the location of the maximum raster value
        if max_point is not None:
            feature.setGeometry(QgsGeometry.fromPointXY(max_point))
            output_provider.addFeature(feature)
    
    # Save the output shapefile
    output_provider.addFeatures([f for f in point_layer.getFeatures()])
    output_layer.updateExtents()

    return output_layer
