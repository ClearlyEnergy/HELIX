/**
 * :copyright (c) 2014 - 2017, The Regents of the University of California, through Lawrence Berkeley National Laboratory (subject to receipt of any required approvals from the U.S. Department of Energy) and contributors. All rights reserved.
 * :author
 */
angular.module('BE.seed.controller.export_inventory_modal', []).controller('export_inventory_modal_controller', [
  '$scope', '$uibModalInstance', 'gridApi', 'uiGridExporterConstants', '$http', function ($scope, $uibModalInstance, gridApi, uiGridExporterConstants, $http) {
    $scope.gridApi = gridApi;
    $scope.export_name = '';
    $scope.export_type = 'csv';

    $scope.export_selected = function () {
      var filename = $scope.export_name;

      //Begin HELIX changes
      if ($scope.export_type = 'helix_csv') {
        selected_views = $scope.gridApi.selection.getSelectedRows().map(function(e){return e.id}).toString();
        window.open('/helix/helix-csv-export/?view_ids='+selected_views+'&file_name='+filename);
        return;
      }
      //End changes
      var ext = '.' + $scope.export_type;

      if (!_.endsWith(filename, ext)) filename += ext;
      $scope.gridApi.grid.options.exporterCsvFilename = filename;
      $scope.gridApi.exporter.csvExport(uiGridExporterConstants.SELECTED, uiGridExporterConstants.VISIBLE);
      $uibModalInstance.close();
    };

    $scope.cancel = function () {
      $uibModalInstance.dismiss('cancel');
    };

    $scope.close = function () {
      $uibModalInstance.close();
    };
  }]);
