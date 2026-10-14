function RandomizedQuestionStudioView(runtime, element, initData) {
    var $el = $(element);
    var data = initData || {};

    var saveUrl = runtime.handlerUrl(element, 'studio_submit');

    // Populate initial inputs
    $el.find('#rq-display-name').val(data.display_name || '');
    $el.find('#rq-prompt').val(data.prompt || '');
    $el.find('#rq-param-t').val(data.total_options_count || 4);
    $el.find('#rq-param-c').val(data.correct_options_count || 2);
    $el.find('#rq-fail-wrong').prop('checked', data.fail_on_any_wrong !== false);
    $el.find('#rq-fail-incomplete').prop('checked', data.fail_if_not_all_correct !== false);
    $el.find('#rq-fallback-score').val(data.grading_default_score !== undefined ? data.grading_default_score : 0.0);
    $el.find('#rq-weight').val(data.weight !== undefined ? data.weight : 1.0);
    $el.find('#rq-max-attempts').val(data.max_attempts || 3);
    $el.find('#rq-show-correctness').val(data.show_correctness || 'always');
    $el.find('#rq-explanation').val(data.explanation || '');

    function renderPool(listSelector, items, isCorrect) {
        var $list = $el.find(listSelector);
        $list.empty();
        (items || []).forEach(function(itemText, idx) {
            var $row = $('<div class="pool-item-row"></div>');
            var $input = $('<input type="text" class="form-control pool-item-input">').val(itemText);
            var $btnRemove = $('<button type="button" class="btn btn-sm btn-danger">&times;</button>');

            $btnRemove.on('click', function() {
                $row.remove();
                updatePoolCounts();
                validateConstraintsLive();
            });

            $input.on('input', function() {
                validateConstraintsLive();
            });

            $row.append($input).append($btnRemove);
            $list.append($row);
        });
        updatePoolCounts();
    }

    function addPoolItem(listSelector) {
        var $list = $el.find(listSelector);
        var $row = $('<div class="pool-item-row"></div>');
        var $input = $('<input type="text" class="form-control pool-item-input" placeholder="Enter option text...">');
        var $btnRemove = $('<button type="button" class="btn btn-sm btn-danger">&times;</button>');

        $btnRemove.on('click', function() {
            $row.remove();
            updatePoolCounts();
            validateConstraintsLive();
        });

        $input.on('input', function() {
            validateConstraintsLive();
        });

        $row.append($input).append($btnRemove);
        $list.append($row);
        $input.focus();
        updatePoolCounts();
        validateConstraintsLive();
    }

    function getPoolValues(listSelector) {
        var values = [];
        $el.find(listSelector + ' .pool-item-input').each(function() {
            var val = $(this).val().trim();
            if (val) {
                values.push(val);
            }
        });
        return values;
    }

    function updatePoolCounts() {
        var cCount = getPoolValues('.list-pool-c').length;
        var iCount = getPoolValues('.list-pool-i').length;
        $el.find('.pool-c-count').text(cCount + ' item' + (cCount === 1 ? '' : 's'));
        $el.find('.pool-i-count').text(iCount + ' item' + (iCount === 1 ? '' : 's'));
    }

    // Piecewise Cases Builder
    var casesList = (data.grading_cases && data.grading_cases.length > 0) ? JSON.parse(JSON.stringify(data.grading_cases)) : [];

    function renderCasesTable() {
        var $tbody = $el.find('#cases-table-body');
        $tbody.empty();

        casesList.forEach(function(c, idx) {
            var $tr = $('<tr></tr>');

            // Description
            var $descTd = $('<td></td>');
            var $descInput = $('<input type="text" class="form-control case-desc">').val(c.description || '');
            $descTd.append($descInput);

            // Condition Type
            var $typeTd = $('<td></td>');
            var $typeSelect = $('<select class="form-control case-type"></select>')
                .append('<option value="all_correct">All displayed correct (x == c)</option>')
                .append('<option value="exact_correct">Exactly k correct (x == k)</option>')
                .append('<option value="min_correct">At least k correct (x >= k)</option>')
                .append('<option value="custom_expr">Custom expression (e.g. x==2 and w==0)</option>')
                .val(c.condition_type || 'all_correct');
            $typeTd.append($typeSelect);

            // Target Value
            var $valTd = $('<td></td>');
            var $valInput = $('<input type="text" class="form-control case-val">').val(c.condition_value !== null && c.condition_value !== undefined ? c.condition_value : '');
            if (c.condition_type === 'all_correct') {
                $valInput.prop('disabled', true).attr('placeholder', 'N/A (all)');
            }
            $valTd.append($valInput);

            $typeSelect.on('change', function() {
                var selectedType = $(this).val();
                if (selectedType === 'all_correct') {
                    $valInput.prop('disabled', true).val('').attr('placeholder', 'N/A (all)');
                } else if (selectedType === 'custom_expr') {
                    $valInput.prop('disabled', false).attr('placeholder', 'e.g. x==2 and w==0');
                } else {
                    $valInput.prop('disabled', false).attr('placeholder', 'e.g. 1');
                }
            });

            // Score Fraction
            var $scoreTd = $('<td></td>');
            var $scoreInput = $('<input type="number" class="form-control case-score" min="0" max="100" step="5">')
                .val(Math.round((c.score_fraction !== undefined ? c.score_fraction : 1.0) * 100));
            $scoreTd.append($scoreInput);

            // Actions
            var $actTd = $('<td></td>');
            var $btnDel = $('<button type="button" class="btn btn-sm btn-danger">Delete</button>');
            $btnDel.on('click', function() {
                casesList.splice(idx, 1);
                renderCasesTable();
            });
            $actTd.append($btnDel);

            $tr.append($descTd).append($typeTd).append($valTd).append($scoreTd).append($actTd);
            $tbody.append($tr);
        });
    }

    function addCase() {
        casesList.push({
            id: 'case_' + Date.now(),
            description: 'Custom case ' + (casesList.length + 1),
            condition_type: 'all_correct',
            condition_value: null,
            max_wrong_allowed: 0,
            score_fraction: 1.0,
            feedback: 'Graded via custom case rule.'
        });
        renderCasesTable();
    }

    function validateConstraintsLive() {
        var cList = getPoolValues('.list-pool-c');
        var iList = getPoolValues('.list-pool-i');
        var t = parseInt($el.find('#rq-param-t').val(), 10) || 0;
        var c = parseInt($el.find('#rq-param-c').val(), 10) || 0;

        var errors = [];
        if (cList.length < 1) {
            errors.push('Pool C must have at least 1 correct answer.');
        }
        var totalAvailable = cList.length + iList.length;
        if (totalAvailable < 2) {
            errors.push('Total options available (|C| + |I|) must be at least 2.');
        }
        if (c < 1 || c > cList.length) {
            errors.push('Correct count (c=' + c + ') must satisfy 1 <= c <= |C| (current |C|=' + cList.length + ').');
        }
        if (t < 2 || t > totalAvailable) {
            errors.push('Total count (t=' + t + ') must satisfy 2 <= t <= |C|+|I| (current total=' + totalAvailable + ').');
        }
        if (t - c < 0) {
            errors.push('Total count (t=' + t + ') cannot be smaller than correct count (c=' + c + ').');
        }
        if ((t - c) > iList.length) {
            errors.push('Required incorrect answers (t - c = ' + (t - c) + ') exceeds available pool |I| (' + iList.length + ').');
        }

        var $banner = $el.find('#pool-validation-banner');
        if (errors.length > 0) {
            $banner.html('<strong>Validation Warning:</strong><br>' + errors.join('<br>')).show();
            return false;
        } else {
            $banner.hide();
            return true;
        }
    }

    // Event Bindings
    $el.find('.btn-add-c').on('click', function() { addPoolItem('.list-pool-c'); });
    $el.find('.btn-add-i').on('click', function() { addPoolItem('.list-pool-i'); });
    $el.find('.btn-add-case').on('click', addCase);
    $el.find('#rq-param-t, #rq-param-c').on('input change', validateConstraintsLive);

    $el.find('.btn-save').on('click', function() {
        var cList = getPoolValues('.list-pool-c');
        var iList = getPoolValues('.list-pool-i');
        var t = parseInt($el.find('#rq-param-t').val(), 10);
        var c = parseInt($el.find('#rq-param-c').val(), 10);

        if (!validateConstraintsLive()) {
            alert('Please fix the validation errors before saving.');
            return;
        }

        // Build cases array from table rows
        var compiledCases = [];
        $el.find('#cases-table-body tr').each(function(idx) {
            var $row = $(this);
            var desc = $row.find('.case-desc').val().trim() || ('Case ' + (idx + 1));
            var type = $row.find('.case-type').val();
            var valRaw = $row.find('.case-val').val().trim();
            var scorePct = parseFloat($row.find('.case-score').val()) || 0;

            var condVal = null;
            if (type === 'exact_correct' || type === 'min_correct') {
                condVal = parseInt(valRaw, 10) || 1;
            } else if (type === 'custom_expr') {
                condVal = valRaw;
            }

            compiledCases.push({
                id: 'case_' + (idx + 1),
                description: desc,
                condition_type: type,
                condition_value: condVal,
                max_wrong_allowed: 0,
                score_fraction: Math.max(0, Math.min(1.0, scorePct / 100.0)),
                feedback: 'Matched case: ' + desc
            });
        });

        var payload = {
            display_name: $el.find('#rq-display-name').val(),
            prompt: $el.find('#rq-prompt').val(),
            correct_answers: cList,
            incorrect_answers: iList,
            total_options_count: t,
            correct_options_count: c,
            fail_on_any_wrong: $el.find('#rq-fail-wrong').is(':checked'),
            fail_if_not_all_correct: $el.find('#rq-fail-incomplete').is(':checked'),
            grading_default_score: parseFloat($el.find('#rq-fallback-score').val()) || 0.0,
            grading_cases: compiledCases,
            weight: parseFloat($el.find('#rq-weight').val()) || 1.0,
            max_attempts: parseInt($el.find('#rq-max-attempts').val(), 10) || 3,
            show_correctness: $el.find('#rq-show-correctness').val(),
            explanation: $el.find('#rq-explanation').val()
        };

        var $status = $el.find('.save-status');
        $status.css('color', '#3182ce').text('Saving...');

        $.ajax({
            type: 'POST',
            url: saveUrl,
            data: JSON.stringify(payload),
            contentType: 'application/json; charset=utf-8',
            dataType: 'json',
            success: function(resp) {
                if (resp.success) {
                    $status.css('color', '#38a169').text('Saved successfully!');
                    setTimeout(function() {
                        if (runtime.notify) {
                            runtime.notify('save', { state: 'end' });
                        }
                    }, 500);
                } else {
                    $status.css('color', '#e53e3e').text('Error: ' + resp.error);
                }
            },
            error: function(err) {
                $status.css('color', '#e53e3e').text('Server error saving settings.');
            }
        });
    });

    $el.find('.btn-cancel').on('click', function() {
        if (runtime.notify) {
            runtime.notify('cancel', {});
        }
    });

    // Initial render
    renderPool('.list-pool-c', data.correct_answers || [], true);
    renderPool('.list-pool-i', data.incorrect_answers || [], false);
    renderCasesTable();
    validateConstraintsLive();
}
