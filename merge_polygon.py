import os
os.environ['USE_PATH_FOR_GDAL_PYTHON'] = 'YES'
from osgeo import ogr,osr
from loguru import logger
from tqdm import tqdm
import json
from rtree.index import Index

def feat_makevalid(feat:ogr.Feature):
    feat_list = []
    geom:ogr.Geometry = feat.GetGeometryRef()
    if geom.IsValid():
        return [feat]
    geom2:ogr.Geometry = geom.MakeValid()
    geomlist = get_polygon(geom2)
    for _g in geomlist:
        f:ogr.Feature = feat.Clone()
        f.SetGeometry(_g)
        feat_list.append(f)
    return feat_list

def get_polygon(geom:ogr.Geometry):
    geomlist = []
    
    geom_type = geom.GetGeometryType()
    
    if geom_type==ogr.wkbPolygon:
        geomlist.append(geom)
    elif geom_type in [ogr.wkbMultiPolygon,ogr.wkbGeometryCollection]:
        for i in range(geom.GetGeometryCount()):
            geomlist+=get_polygon(geom.GetGeometryRef(i))
    elif geom_type in (ogr.wkbLineString,ogr.wkbMultiLineString,ogr.wkbPoint):
        pass
    else:
        logger.info(ogr.GeometryTypeToName(geom_type))
    
    # for i in range(geom.GetGeometryCount()):
    #     _geom:ogr.Geometry = geom.GetGeometryRef(i)
    #     if _geom.GetGeometryCount()==1:
    #         if _geom.GetGeometryType()==ogr.wkbPolygon: 
    #             geomlist.append(_geom)
    #         elif _geom.GetGeometryType()==ogr.wkbMultiPolygon:
    #             geomlist+=get_polygon(_geom)

    #     else:
    #         geomlist+=get_polygon(_geom)

    return geomlist



def MergePolygon(src,dst,ident_flds=['category']):
    ds:ogr.DataSource = ogr.Open(src)
    lyr:ogr.Layer = ds.GetLayerByIndex(0)
    bounds = lyr.GetExtent()
    feat_count = lyr.GetFeatureCount()

    s_index = Index(bounds = bounds)
    feat_list = []
    deleted_id_list = []
    _feat_orgin:ogr.Feature = lyr.GetNextFeature()
    pbar = tqdm(total=feat_count)
    _id = 0
    while _feat_orgin:
        feat_list_valied = feat_makevalid(_feat_orgin)
        for feat in (feat_list_valied):
            geom:ogr.Geometry = feat.GetGeometryRef()
            if geom.GetArea()>0:
                # logger.info(geom.ExportToWkt())
                env = feat.GetGeometryRef().GetEnvelope()
                bbox = (env[0],env[2],env[1],env[3])
                intersection_list :list[ogr.Feature] = s_index.intersection(bbox)
                is_same_kind = False
                for _id in intersection_list :
                    f = feat_list[_id]
                    is_same_kind = geom.Intersects(f.GetGeometryRef())
                    if is_same_kind :
                        for fld in ident_flds:
                            is_same_kind = is_same_kind & (f.GetField(fld)==feat.GetField(fld))
                        if is_same_kind :
                            _env_temp= f.GetGeometryRef().GetEnvelope()
                            _bbox_temp = (_env_temp[0],_env_temp[2],_env_temp[1],_env_temp[3])
                            s_index.delete(_id,_bbox_temp)
                            geom = geom.Union(f.GetGeometryRef())
                            # feat.SetGeometry(geom2)
                            deleted_id_list.append(_id)
                feat.SetGeometry(geom)
                feat_list.append(feat)
                _id = len(feat_list)-1
                env = geom.GetEnvelope()
                bbox = (env[0],env[2],env[1],env[3])
                s_index.insert(_id,bbox)
        _feat_orgin = lyr.GetNextFeature()
        pbar.update(1)
    pbar = None
    logger.info(f'合并计算完成,数量：{len(feat_list)}，开始输出')

    result_list = [f for i,f in enumerate(feat_list) if i not in deleted_id_list]
    logger.info(f'过滤完成,数量：{len(result_list)}，开始输出')

    drv_out :ogr.Driver = ds.GetDriver()
    ds_out:ogr.DataSource = drv_out.CreateDataSource(dst)
    lyr_out:ogr.Layer=ds_out.CreateLayer(lyr.GetName(),srs=lyr.GetSpatialRef(),geom_type=lyr.GetGeomType())
    has_no_srs = lyr_out.GetSpatialRef() is None
    geom_count = 0
    for f in result_list:
        geom_list = get_polygon(f.GetGeometryRef())
        geom_count+=len(geom_list)
        for geom in geom_list:
            _f = f.Clone()
            _f.SetGeometry(geom)
            lyr_out.CreateFeature(_f)
    
    logger.info(f'输出完成,数量：{geom_count}')

    
    ds_out.FlushCache()
    ds_out = None

    srs:osr.SpatialReference= lyr.GetSpatialRef()
    if srs is not None and has_no_srs:
        proj = srs.ExportToProj4()
        write_srs(dst,proj)

        logger.info('写入坐标系成功')

    


    


def get_srs(f):
    with open(f,'r',encoding='utf-8') as txt:
        obj = json.loads(txt.read())
        print(obj.keys())

def write_srs(f,srs_proj):
    obj = None
    with open(f,'r',encoding='utf-8') as txt:
        obj = json.loads(txt.read())
    
    if obj:
        obj['crs']={'type':'name','properties':{'name':srs_proj}}
        with open(f,'w',encoding='utf-8') as txt:
            txt.write(json.dumps(obj,ensure_ascii=False))


# index = Index()



if __name__ =='__main__':

    geojson = r'out\2.3.geojson'
    geojson_merged = r'out\2.3_merged5.geojson'

    # get_srs(geojson)

    # geojson = r'out\test_water.geojson'
    # geojson_merged = r'out\test_water_merged2.geojson'
    if os.path.exists(geojson_merged):
        os.remove(geojson_merged)
    MergePolygon(geojson,geojson_merged)




