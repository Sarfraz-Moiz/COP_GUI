import QtQuick
import QtQuick.Controls
import QtLocation
import QtPositioning

Item {
    id: root
    property real centerLatitude: 0
    property real centerLongitude: 0
    property real requestedZoom: 14
    property bool satelliteMode: false
    property bool satelliteAvailable: false
    property string mapModeLabel: satelliteMode && satelliteAvailable ? "SATELLITE" : "STREET"

    function applyMapType() {
        var wanted = satelliteMode ? MapType.SatelliteMapDay : MapType.StreetMap
        for (var i = 0; i < map.supportedMapTypes.length; ++i) {
            if (map.supportedMapTypes[i].style === wanted) {
                map.activeMapType = map.supportedMapTypes[i]
                root.satelliteAvailable = satelliteMode && wanted === MapType.SatelliteMapDay
                return true
            }
        }
        if (map.supportedMapTypes.length > 0) {
            map.activeMapType = map.supportedMapTypes[0]
            root.satelliteAvailable = false
            return false
        }
        return false
    }

    Plugin {
        id: osmPlugin
        name: "osm"
        PluginParameter { name: "osm.useragent"; value: "CentralCameraMonitor/1.0" }
        PluginParameter { name: "osm.mapping.host"; value: "https://tile.openstreetmap.org/" }
        PluginParameter { name: "osm.mapping.copyright"; value: "© OpenStreetMap contributors" }
        PluginParameter { name: "osm.mapping.providersrepository.disabled"; value: "false" }
        PluginParameter { name: "osm.mapping.cache.directory"; value: mapCacheDirectory }
        PluginParameter { name: "osm.mapping.cache.disk.cost_strategy"; value: "bytesize" }
        PluginParameter { name: "osm.mapping.cache.disk.size"; value: 268435456 }
        PluginParameter { name: "osm.mapping.cache.memory.cost_strategy"; value: "bytesize" }
        PluginParameter { name: "osm.mapping.cache.memory.size"; value: 33554432 }
        PluginParameter { name: "osm.mapping.prefetching_style"; value: "TwoNeighbourLayers" }
    }

    Map {
        id: map
        anchors.fill: parent
        plugin: osmPlugin
        center: QtPositioning.coordinate(root.centerLatitude, root.centerLongitude)
        zoomLevel: root.requestedZoom
        copyrightsVisible: true
        activeMapType: null

        Component.onCompleted: root.applyMapType()
        onSupportedMapTypesChanged: root.applyMapType()

        // Camera FOV sectors.
        MapItemView {
            model: fovModel
            delegate: MapPolygon {
                path: [
                    QtPositioning.coordinate(model.p1lat, model.p1lon),
                    QtPositioning.coordinate(model.p2lat, model.p2lon),
                    QtPositioning.coordinate(model.p3lat, model.p3lon)
                ]
                color: Qt.rgba(0.08, 0.55, 0.95, 0.08)
                border.color: model.color
                border.width: 1
            }
        }

        // Camera-to-target links.
        MapItemView {
            model: linkModel
            delegate: MapPolyline {
                path: [
                    QtPositioning.coordinate(model.lat1, model.lon1),
                    QtPositioning.coordinate(model.lat2, model.lon2)
                ]
                line.color: model.color
                line.width: 2
            }
        }

        // Camera heading vectors.
        MapItemView {
            model: headingModel
            delegate: MapPolyline {
                path: [
                    QtPositioning.coordinate(model.lat1, model.lon1),
                    QtPositioning.coordinate(model.lat2, model.lon2)
                ]
                line.color: model.color
                line.width: 3
            }
        }

        // Target markers.
        MapItemView {
            model: targetModel
            delegate: MapQuickItem {
                coordinate: QtPositioning.coordinate(model.lat, model.lon)
                anchorPoint.x: 9
                anchorPoint.y: 9
                sourceItem: Item {
                    width: 18; height: 18
                    Rectangle {
                        width: 14; height: 14
                        anchors.centerIn: parent
                        rotation: 45
                        color: model.color
                        border.color: "white"
                        border.width: 1
                    }
                    Rectangle {
                        width: 4; height: 4
                        anchors.centerIn: parent
                        radius: 2
                        color: "white"
                    }
                    Label {
                        anchors.left: parent.right
                        anchors.leftMargin: 5
                        anchors.verticalCenter: parent.verticalCenter
                        text: model.id
                        color: "white"
                        font.pixelSize: 11
                        font.bold: true
                        style: Text.Outline
                        styleColor: "#07111d"
                    }
                }
            }
        }

        // Camera markers.
        MapItemView {
            model: cameraModel
            delegate: MapQuickItem {
                coordinate: QtPositioning.coordinate(model.lat, model.lon)
                anchorPoint.x: 11
                anchorPoint.y: 11
                sourceItem: Item {
                    width: 22; height: 22
                    Rectangle {
                        anchors.fill: parent
                        radius: 11
                        color: model.color
                        border.color: "white"
                        border.width: 2
                    }
                    Text {
                        anchors.centerIn: parent
                        text: "C"
                        color: "#07111d"
                        font.pixelSize: 10
                        font.bold: true
                    }
                    Label {
                        anchors.left: parent.right
                        anchors.leftMargin: 6
                        anchors.verticalCenter: parent.verticalCenter
                        text: model.id
                        color: "white"
                        font.pixelSize: 11
                        font.bold: true
                        style: Text.Outline
                        styleColor: "#07111d"
                    }
                }
            }
        }

        // Mouse pan. Qt Location 6.11 keeps Map itself intentionally minimal;
        // pan()/zoomLevel are used here to provide desktop interaction without
        // requiring the QML MapView wrapper.
        MouseArea {
            anchors.fill: parent
            property point lastPoint
            acceptedButtons: Qt.LeftButton
            onPressed: function(mouse) {
                lastPoint = Qt.point(mouse.x, mouse.y)
            }
            onPositionChanged: function(mouse) {
                if (pressed) {
                    map.pan(mouse.x - lastPoint.x, mouse.y - lastPoint.y)
                    lastPoint = Qt.point(mouse.x, mouse.y)
                }
            }
            onDoubleClicked: function(mouse) {
                if (mouse.button === Qt.LeftButton)
                    map.zoomLevel = Math.min(map.maximumZoomLevel, map.zoomLevel + 1)
            }
        }

        WheelHandler {
            onWheel: function(event) {
                if (event.angleDelta.y > 0)
                    map.zoomLevel = Math.min(map.maximumZoomLevel, map.zoomLevel + 1)
                else
                    map.zoomLevel = Math.max(map.minimumZoomLevel, map.zoomLevel - 1)
                event.accepted = true
            }
        }
    }

    Connections {
        target: root
        function onSatelliteModeChanged() { root.applyMapType() }
    }

    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 10
        width: 270
        height: 60
        radius: 7
        color: "#d90b1118"
        border.color: "#44566a"
        border.width: 1
        Column {
            anchors.fill: parent
            anchors.margins: 8
            spacing: 2
            Text { text: "LIVE MAP"; color: "#f8fafc"; font.bold: true; font.pixelSize: 12 }
            Text { text: root.centerLatitude.toFixed(5) + "  |  " + root.centerLongitude.toFixed(5); color: "#b9cadb"; font.pixelSize: 10 }
            Text { text: root.mapModeLabel + " • NETWORK + LOCAL TILE CACHE"; color: "#71879c"; font.pixelSize: 9 }
        }
    }

    Rectangle {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 10
        width: 42; height: 86
        radius: 6
        color: "#d90b1118"
        border.color: "#44566a"
        Column {
            anchors.fill: parent
            spacing: 1
            Button { width: 42; height: 42; text: "+"; onClicked: map.zoomLevel = Math.min(map.maximumZoomLevel, map.zoomLevel + 1) }
            Button { width: 42; height: 42; text: "−"; onClicked: map.zoomLevel = Math.max(map.minimumZoomLevel, map.zoomLevel - 1) }
        }
    }

    Rectangle {
        visible: root.satelliteMode && !root.satelliteAvailable
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.margins: 10
        width: 190
        height: 28
        radius: 4
        color: "#d91f2937"
        Text { anchors.fill: parent; anchors.margins: 6; text: "Satellite provider unavailable"; color: "#fecaca"; font.pixelSize: 9 }
    }
}
