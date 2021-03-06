import csv
from collections import OrderedDict

from django.db import transaction
from django.utils.translation import ugettext as _
from party.models import Party, TenureRelationship, TenureRelationshipType
from spatial.models import SpatialUnit
from xforms.utils import odk_geom_to_wkt

from . import base, exceptions

CONTENT_TYPES = {
    'spatial.spatialunit': 'Spatial Unit',
    'spatial.spatialrelationship': 'Spatial Relationship',
    'party.party': 'Party',
    'party.tenurerelationship': 'Tenure Relationship',
    'party.partyrelationship': 'Party Relationship'
}
GEOMETRY_TYPES = ['', 'geopoint', 'geotrace', 'geoshape']
TENURE_TYPE = 'tenure_type'


class CSVImporter(base.Importer):

    def __init__(self, project=None, path=None,
                 delimiter=None, quotechar=None):
        super(CSVImporter, self).__init__(project=project)
        self.path = path
        self.delimiter = ',' if not delimiter else delimiter
        self.quotechar = '|' if not quotechar else quotechar

    def get_headers(self):
        headers = []
        with open(self.path, 'r', newline='') as csvfile:
            reader = csv.reader(
                csvfile, delimiter=self.delimiter, quotechar=self.quotechar
            )
            head = next(reader)
        headers = [
            h for h in head if not h.startswith(('_', 'meta/')) and
            h not in base.EXCLUDE_HEADERS
        ]
        return headers

    def get_attribute_map(self):
        headers = sorted([h.lower() for h in self.get_headers()])
        attribute_map = OrderedDict({})
        extra_attrs = []
        extra_headers = []
        schema_attrs = self.get_schema_attrs()
        found_attrs = {}
        for content_type in schema_attrs:
            attributes = schema_attrs[content_type]
            for attr in attributes:
                name = attr.name.lower()
                if name in headers:
                    found_attrs[name] = (
                        attr, content_type, CONTENT_TYPES[content_type])
                else:
                    extra_attrs.append(name)
        for header in headers:
            attr = found_attrs.get(header)
            if attr is not None:
                attribute_map[header] = found_attrs.get(header)
            else:
                extra_headers.append(header)

        return (attribute_map,
                sorted(extra_attrs), sorted(extra_headers))

    def import_data(self, config_dict, **kwargs):
        content_types = dict(
            (key, {}) for key in self.get_content_type_keys())
        (attr_map,
            extra_attrs, extra_headers) = self.get_attribute_map()
        attributes = config_dict['attributes']
        party_name_field = config_dict['party_name_field']
        party_type = config_dict['party_type']
        location_type = config_dict['location_type']
        geometry_type_field = config_dict['geometry_type_field']
        geometry_field = config_dict['geometry_field']
        path = config_dict['file']
        try:
            with transaction.atomic():
                with open(path, 'r', newline='') as csvfile:
                    reader = csv.reader(
                        csvfile, delimiter=self.delimiter,
                        quotechar=self.quotechar
                    )
                    csv_headers = [h.lower() for h in next(reader)]
                    for row in reader:
                        if len(csv_headers) != len(row):
                            raise ValueError(
                                _("Number of headers and columns "
                                  "do not match")
                            )
                        party_name = row[csv_headers.index(party_name_field)]
                        coords = row[csv_headers.index(geometry_field)]
                        geometry_type = row[csv_headers.index(
                                            geometry_type_field)]
                        if geometry_type not in GEOMETRY_TYPES:
                            raise ValueError(
                                _("Invalid geometry type")
                            )
                        geometry = odk_geom_to_wkt(coords)
                        try:
                            tenure_type = row[
                                csv_headers.index(TENURE_TYPE)]
                        except ValueError as e:
                            raise ValueError(
                                _("No 'tenure_type' column found")
                            )
                        content_types['party.party'] = {
                            'project': self.project,
                            'name': party_name,
                            'type': party_type,
                            'attributes': {}
                        }
                        content_types['spatial.spatialunit'] = {
                            'project': self.project,
                            'type': location_type,
                            'geometry': geometry,
                            'attributes': {}
                        }
                        for attr in attributes:
                            attribute, content_type, name = attr_map.get(attr)
                            if (attribute is not None):
                                val = row[csv_headers.index(attr)]
                                if (not attribute.required and val == ""):
                                    continue
                                content_types[content_type][
                                    'attributes'][
                                        attribute.name] = val
                        party = Party.objects.create(
                            **content_types['party.party']
                        )
                        su = SpatialUnit.objects.create(
                            **content_types['spatial.spatialunit']
                        )
                        tt = TenureRelationshipType.objects.get(id=tenure_type)
                        TenureRelationship.objects.create(
                            project=self.project, party=party,
                            spatial_unit=su, tenure_type=tt
                        )
        except Exception as e:
            raise exceptions.DataImportError(
                line_num=reader.line_num, error=e)
