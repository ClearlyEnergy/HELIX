/*
 * :copyright (c) 2014 - 2017, 
 * :author
 * DOES NOTHING !!!
 */
angular.module('BE.seed.controller.green_assessments', [])
  .controller('green_assessments_controller', [
    '$scope',
    'organization_payload',
	  function ($scope, organization_payload) {
      var init = function () {
        $scope.orgs = organization_payload.organizations;
        $scope.orgs_I_own = organization_payload.organizations.filter(function (o) {
          return o.user_is_owner;
        });
      };
      init();
	  console.log($scope.orgs)
    }
  ]);
