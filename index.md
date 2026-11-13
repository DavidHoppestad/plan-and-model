---
title: Plan & Model
---

# Plan & Model

Scan a room with the LiDAR scanner on your iPhone or iPad. Plan & Model makes a dimensioned floor
plan, wall elevations, a furniture layout and 3D files, saved as ordinary files in your iCloud
Drive so you can open them in Claude, Blender and FreeCAD on your Mac.

- Scanning needs an iPhone or iPad with a LiDAR scanner. Other devices can view, edit and export
  scans made on a LiDAR device with the same Apple Account.
- Free: unlimited scans, floor plans (PDF, PNG, SVG), the 3D scene (USDZ) and files for Claude.
- Pro (subscription): CAD and BIM files (DXF, IFC, FreeCAD), 3D meshes (OBJ, STL, PLY, glTF) and
  extra drawing sheets. Files you make while subscribed stay yours.

{% assign links = site.pages | where_exp: "p", "p.nav" | sort: "nav" %}
{% for p in links %}[{{ p.title }}]({{ p.url | relative_url }}){% unless forloop.last %} · {% endunless %}{% endfor %}
