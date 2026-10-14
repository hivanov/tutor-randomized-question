function RandomizedQuestionStudentView(runtime, element, initData) {
    var $el = $(element);
    var data = initData || {};

    var submitUrl = runtime.handlerUrl(element, 'submit_answer');
    var resetUrl = runtime.handlerUrl(element, 'reset_problem');

    function renderView() {
        $el.find('.problem-title').text(data.display_name || 'Question');
        $el.find('.problem-prompt').html(data.prompt || '');
        
        var isSingle = data.is_single_choice || false;
        $el.find('.instruction-text').text(
            isSingle ? 'Choose the single best answer.' : 'Select all options that apply.'
        );

        $el.find('.attempts-badge').text('Attempts: ' + (data.attempts || 0) + ' / ' + (data.max_attempts || 3));
        $el.find('.points-badge').text('Weight: ' + (data.weight || 1.0) + ' pt' + (data.weight === 1.0 ? '' : 's'));

        var $optionsContainer = $el.find('.options-container');
        $optionsContainer.empty();

        var inputType = isSingle ? 'radio' : 'checkbox';
        var selectedSet = new Set(data.selected_ids || []);

        (data.options || []).forEach(function(opt) {
            var isChecked = selectedSet.has(opt.id);
            var $item = $('<div class="option-item"></div>');
            if (isChecked) {
                $item.addClass('selected');
            }

            var $input = $('<input class="option-input">')
                .attr('type', inputType)
                .attr('name', 'option_' + runtime.elementId)
                .attr('value', opt.id)
                .prop('checked', isChecked);

            if (data.attempts >= data.max_attempts && data.completed) {
                $input.prop('disabled', true);
            }

            var $label = $('<label class="option-label"></label>')
                .text(opt.text);

            $item.append($input).append($label);

            $item.on('click', function(e) {
                if ($input.prop('disabled')) return;
                if (e.target !== $input[0]) {
                    if (isSingle) {
                        $input.prop('checked', true).trigger('change');
                    } else {
                        $input.prop('checked', !$input.prop('checked')).trigger('change');
                    }
                }
            });

            $input.on('change', function() {
                if (isSingle) {
                    $optionsContainer.find('.option-item').removeClass('selected');
                    if ($input.prop('checked')) {
                        $item.addClass('selected');
                    }
                } else {
                    $item.toggleClass('selected', $input.prop('checked'));
                }
            });

            $optionsContainer.append($item);
        });

        // Submit / Reset buttons
        if (data.attempts >= data.max_attempts) {
            $el.find('.btn-submit').prop('disabled', true);
            $el.find('.btn-reset').hide();
        } else {
            $el.find('.btn-submit').prop('disabled', false);
            if (data.completed && data.attempts < data.max_attempts) {
                $el.find('.btn-reset').show();
            } else {
                $el.find('.btn-reset').hide();
            }
        }

        // Show feedback if already completed
        if (data.completed) {
            showFeedback({
                score: data.score,
                max_score: data.weight,
                is_correct: data.raw_score_fraction >= 1.0,
                feedback: data.last_feedback,
                explanation: data.explanation
            });
        }
    }

    function showFeedback(result) {
        var $fbContainer = $el.find('.feedback-container');
        var $fbAlert = $fbContainer.find('.feedback-alert');
        $fbAlert.removeClass('alert-success alert-warning alert-danger');

        var isCorrect = result.is_correct || result.score >= result.max_score;
        var isPartial = result.score > 0 && result.score < result.max_score;

        if (isCorrect) {
            $fbAlert.addClass('alert-success');
            $fbAlert.find('.feedback-title').text('Correct (' + result.score + ' / ' + result.max_score + ' pts)');
        } else if (isPartial) {
            $fbAlert.addClass('alert-warning');
            $fbAlert.find('.feedback-title').text('Partially Correct (' + result.score + ' / ' + result.max_score + ' pts)');
        } else {
            $fbAlert.addClass('alert-danger');
            $fbAlert.find('.feedback-title').text('Incorrect (0 / ' + result.max_score + ' pts)');
        }

        $fbAlert.find('.feedback-message').text(result.feedback || '');
        $fbContainer.slideDown(200);

        if (result.explanation) {
            $el.find('.explanation-content').text(result.explanation);
            $el.find('.explanation-container').slideDown(200);
        }
    }

    $el.find('.btn-submit').on('click', function() {
        var selected = [];
        $el.find('.option-input:checked').each(function() {
            selected.push($(this).val());
        });

        if (selected.length === 0) {
            alert('Please select at least one option before submitting.');
            return;
        }

        var $btn = $(this);
        $btn.prop('disabled', true).text('Evaluating...');

        $.ajax({
            type: 'POST',
            url: submitUrl,
            data: JSON.stringify({ selected_ids: selected }),
            contentType: 'application/json; charset=utf-8',
            dataType: 'json',
            success: function(resp) {
                $btn.prop('disabled', false).text('Submit Answer');
                if (resp.success) {
                    data.attempts = resp.attempts;
                    data.completed = true;
                    data.last_feedback = resp.feedback;
                    data.score = resp.score;
                    data.raw_score_fraction = resp.raw_score_fraction;
                    data.selected_ids = selected;
                    data.explanation = resp.explanation;

                    renderView();
                    showFeedback(resp);
                } else {
                    alert('Submission error: ' + (resp.error || 'Unknown error'));
                }
            },
            error: function(err) {
                $btn.prop('disabled', false).text('Submit Answer');
                alert('An error occurred during submission.');
            }
        });
    });

    $el.find('.btn-reset').on('click', function() {
        var $btn = $(this);
        $btn.prop('disabled', true).text('Reseeding...');

        $.ajax({
            type: 'POST',
            url: resetUrl,
            data: JSON.stringify({}),
            contentType: 'application/json; charset=utf-8',
            dataType: 'json',
            success: function(resp) {
                $btn.prop('disabled', false).text('Try New Attempt');
                if (resp.success) {
                    data.options = resp.options;
                    data.selected_ids = [];
                    data.completed = false;
                    $el.find('.feedback-container').slideUp(150);
                    $el.find('.explanation-container').slideUp(150);
                    renderView();
                } else {
                    alert('Reset error: ' + (resp.error || 'Unknown error'));
                }
            },
            error: function() {
                $btn.prop('disabled', false).text('Try New Attempt');
                alert('Failed to reset question.');
            }
        });
    });

    renderView();
}
