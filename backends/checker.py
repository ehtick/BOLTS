# Copyright 2012-2013 Johannes Reinhardt <jreinhardt@ist-dein-freund.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from os import listdir
from os.path import join, exists, basename, splitext

from common import BackendExporter
import license
from errors import *

class ErrorTable:
	def __init__(self,title,description,headers):
		self.title = title
		self.description = description
		self.rows = []
		self.headers = headers

	def populate(self,repo,databases):
		pass

	def get_headers(self):
		return self.headers

	def get_title(self):
		return self.title

	def get_description(self):
		return self.description

	def get_table(self):
		return self.rows

	def print_table(self):
		if len(self.rows) == 0:
			return ""

		res = []
		res.append(self.title)
		res.append('-'*len(self.title) + '\n')
		res.append(self.description + '\n')

		#determine maximum field width
		width = []
		for field in self.headers:
			width.append(len(field))
		for row in self.rows:
			for i in range(len(row)):
				width[i] = max(len(str(row[i])),width[i])

		#add some more space
		for i in range(len(width)):
			width[i] += 2

		#print headers
		res.append("".join("%-*s" % (width[i],self.headers[i]) for i in range(len(self.headers))))
		res.append("".join("-"*w for w in width))

		for row in self.rows:
			res.append("".join("%-*s" % (w,v) for w,v in zip(width,row)))
		res.append("\n")
		return "\n".join(res)


class MissingBaseTable(ErrorTable):
	def __init__(self):
		ErrorTable.__init__(self,
			"Missing base geometries",
			"Some classes can not be used in one or more CAD packages, because no geometry is available.",
			["Class id","Collection","Standards","FreeCAD","OpenSCAD"]
		)

	def populate(self,repo,dbs):
		for coll in repo.collections:
			for cl in coll.classes_by_ids():
				row = []
				row.append(cl.id)
				row.append(coll.id)
				row.append(cl.standard)
				row.append(cl.id in dbs["freecad"].getbase)
				row.append(cl.id in dbs["openscad"].getbase)
				if not (row[-1] and row[-2]):
					self.rows.append(row)

class UnknownClassTable(ErrorTable):
	def __init__(self):
		ErrorTable.__init__(self,
			"Unknown classes",
			"Some classes are mentioned in base files, but never defined in blt files.",
			["Class id", "Database"]
		)

		def populate(self,repo,dbs):
			ids = []
			for coll in repo.collections:
				for cl in coll.classes_by_ids():
					ids.append(cl.id)
			for db in dbs:
				for base in dbs[db].getbase.values():
					for cl_id in base.classids:
						if cl_id not in ids:
							row = []
							row.append(cl_id)
							row.append(db)
							self.rows.append(row)

class MissingCommonParametersTable(ErrorTable):
	def __init__(self):
		ErrorTable.__init__(self,
			"Missing common parameters",
			"Some classes have no common parameters defined.",
			["Class ID","Collection","Standards"]
		)

	def populate(self,repo,dbs):
		for coll in repo.collections:
			for cl in coll.classes_by_ids():
				if len(cl.parameters.common) == 0:
					row = []
					row.append(cl.id)
					row.append(coll.id)
					row.append(cl.standard)
					self.rows.append(row)

class MissingDrawingTable(ErrorTable):
	def __init__(self):
		ErrorTable.__init__(self,
			"Missing drawings",
			"Some classes do not have associated drawings.",
			["Class id", "Collection", "Standards"]
		)

	def populate(self,repo,dbs):
		for coll in repo.collections:
			for cl in coll.classes_by_ids():
				if not cl.id in dbs["drawings"].getbase:
					row = []
					row.append(coll.id)
					row.append(cl.standard)
					self.rows.append(row)

class MissingSVGSourceTable(ErrorTable):
	def __init__(self):
		ErrorTable.__init__(self,
			"Missing svg drawings",
			"Some drawings have no svg version.",
			["Filename", "Class ID"]
		)

	def populate(self,repo,dbs):
		for id,draw in dbs["drawings"].getbase.iteritems():
			if draw.get_svg() is None:
				row = []
				row.append(draw.filename)
				row.append(id)
				self.rows.append(row)

class UnsupportedLicenseTable(ErrorTable):
	def __init__(self):
		ErrorTable.__init__(self,
			"Incompatible Licenses",
			"Some collections or base geometries have unknown licenses.",
			["Type","Id/Filename","License name","License url", "Authors"]
		)

	def populate(self,repo,dbs):
		#collections
		for coll in repo.collections:
			if not license.check_license(coll.license_name,coll.license_url):
				row = []
				row.append("Collection")
				row.append(coll.id)
				row.append(coll.license_name)
				row.append(coll.license_url)
				row.append(",".join(coll.authors))
				self.rows.append(row)
		#bases
		for db in dbs:
			for id, base in dbs[db].getbase.iteritems():
				if not license.check_license(base.license_name,base.license_url):
					row = []
					row.append(db)
					row.append(id)
					row.append(base.license_name)
					row.append(base.license_url)
					row.append(",".join(coll.authors))
					self.rows.append(row)

class UnknownFileTable(ErrorTable):
	def __init__(self):
		ErrorTable.__init__(self,
			"Stray files",
			"Some files are present in the repository, but not mentioned anywhere.",
			["Filename","Path"]
		)

	def populate(self,repo,dbs):
		for db in dbs:
			if db == "drawings":
				continue
			for coll in repo.collections:
				path = join(repo.path,db,coll.id)
				if not exists(path):
					continue
				files = listdir(path)

				#remove files known from bases
				for cl in coll.classes_by_ids():
					if not cl.id in dbs[db].getbase:
						continue
					base = dbs[db].getbase[cl.id]
					if base.filename in files:
						files.remove(base.filename)

				#check what is left
				for filename in files:
					if splitext(filename)[1] == ".base":
						continue
					row = []
					row.append(filename)
					row.append(path)
					self.rows.append(row)

		if "drawings" in dbs:
			for coll in repo.collections:
				path = join(repo.path,"drawings",coll.id)
				if not exists(path):
					continue

				#remove files known from bases
				files = listdir(path)
				for cl in coll.classes_by_ids():
					if not cl.id in dbs["drawings"].getbase:
						continue
					drawing = dbs["drawings"].getbase[cl.id]
					if not drawing.get_png() is None:
						if basename(drawing.get_png()) in files:
							files.remove(basename(drawing.get_png()))
					if not drawing.get_svg() is None:
						if basename(drawing.get_svg()) in files:
							files.remove(basename(drawing.get_svg()))

				#check what is left
				for filename in files:
					if splitext(filename)[1] == ".base":
						continue
					row = []
					row.append(filename)
					row.append(path)
					self.rows.append(row)

class CheckerExporter(BackendExporter):
	def __init__(self,repo,databases):
		BackendExporter.__init__(self,repo)
		self.databases = databases

		self.checks = {}
		self.checks["missingbase"] = MissingBaseTable()
		self.checks["unknownclass"] = UnknownClassTable()
		self.checks["missingcommonparameters"] = MissingCommonParametersTable()
		self.checks["missingdrawing"] = MissingDrawingTable()
		self.checks["missingsvgsource"] = MissingSVGSourceTable()
		self.checks["unsupportedlicense"] = UnsupportedLicenseTable()
		self.checks["unknownfile"] = UnknownFileTable()

		for check in self.checks.values():
			check.populate(repo,databases)

	def write_output(self,out_path):
		pass
