/*
 * :copyright (c) 2014 - 2016, The Regents of the University of California, through Lawrence Berkeley National Laboratory (subject to receipt of any required approvals from the U.S. Department of Energy) and contributors. All rights reserved.
 * :author
 */
angular.module('BE.seed.controller.taxlot_detail', [])
		.controller('taxlot_detail_controller', [
			'$controller',
			'$scope',
			'$routeParams',
			'$uibModal',
			'$log',
			'$filter',
			'$location',
			'property_taxlot_service',
			'taxlot_payload',
			'all_columns',
			'urls',
			'label_helper_service',
			'default_columns',
function($controller, $scope, $routeParams, $uibModal, $log, $filter, $location,
				 	property_taxlot_service, taxlot_payload, all_columns, urls,  label_helper_service, default_columns) {

	$scope.item_type = "taxlot";
	// TODO: Decide what value (address_1?) to show at top of tax lot detail page
	$scope.page_title = "Tax Lot";
	$scope.taxlot = taxlot_payload;
	$scope.item_state = $scope.taxlot.state;
	$scope.user = {};
	$scope.user_role = taxlot_payload.user_role;

	/** Instantiate 'parent' controller class,
	 *  where the more generic methods for a detail item are located.
	 *  (Methods in this child class are more specific to a 'Property' detail item.) */
	$controller('base_detail_controller', { $scope: $scope, $routeParams: $routeParams, $uibModal: $uibModal,
																									$log: $log, property_taxlot_service: property_taxlot_service,
																									all_columns: all_columns, urls: urls, $filter: $filter,
																									$location: $location, label_helper_service: label_helper_service,
																									default_columns: default_columns });


	/* User clicked 'save' button */
	$scope.on_save = function () {
		$scope.save_property();
	}


	/**
	 * restore_property: restores the property from its copy
	 *   and hides the edit fields
	 */
	$scope.restore_copy = function () {
		$scope.property = $scope.item_copy;
		$scope.edit_form_showing = false;
	};


	/**
	 * save_property: saves the property's updates
	 */
	$scope.save_taxlot = function (){
		$scope.$emit('show_saving');
		property_taxlot_service.update_property($scope.taxlot.id, $scope.taxlot.cycle.id, $scope.user_org_id, $scope.taxlot.state)
			.then(function (data){
					$scope.$emit('finished_saving');
				}, function (data, status){
					// reject promise
					$scope.$emit('finished_saving');
				}
			).catch(function (data){
				$log.error( String(data) );
			});
	};

	/**
	 * init: sets default state of property detail page,
	 *   sets the field arrays for each section, performs
	 *   some date string manipulation for better display rendering,
	 *   and gets all the extra_data fields
	 *
	 */
	var init = function() {

		// format date column values
		$scope.format_date_values($scope.taxlot.state, property_taxlot_service.taxlot_state_date_columns);

		// build columns for current Property
		$scope.data_fields = $scope.generate_data_fields($scope.taxlot.state, $scope.default_columns);

		$scope.labels = $scope.init_labels($scope.taxlot);
	};

	// fired on controller loaded
	init();

}]);
