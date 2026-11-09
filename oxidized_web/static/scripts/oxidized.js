var convertTime = function() {
  /* Convert UTC timestamps or ISO/formatted date strings to user's local browser timezone */
  if (typeof dayjs === 'undefined') {
    return;
  }
  if (dayjs.extend && typeof dayjs_plugin_utc !== 'undefined') {
    dayjs.extend(dayjs_plugin_utc);
  }

  $('.time, [data-time]').each(function() {
    var rawText = $(this).text().trim();
    if (!rawText || rawText === 'never' || rawText === 'Never' || rawText === 'unknown' || rawText === '—') {
      return;
    }

    var epoch = $(this).attr('data-epoch') || $(this).attr('epoch');
    var dj;
    if (epoch !== undefined && epoch !== null && epoch !== '') {
      var sec = Number(epoch);
      if (!isNaN(sec) && sec > 0) {
        dj = dayjs.unix(sec);
      }
    } else {
      // Parse ISO or standard YYYY-MM-DD HH:mm:ss strings as UTC
      var cleaned = rawText.replace(' UTC', '');
      if (dayjs.utc) {
        dj = dayjs.utc(cleaned);
      } else {
        dj = dayjs(cleaned);
      }
    }

    if (dj && dj.isValid()) {
      var localDj = dj.local();
      $(this).text(localDj.format('YYYY-MM-DD HH:mm:ss'));
      $(this).attr('title', 'Local Time (Browser: ' + Intl.DateTimeFormat().resolvedOptions().timeZone + ')');
    }
  });
};

$(function() {
  convertTime();

  // Re-run conversion when DataTables redraws or paginates
  $(document).on('draw.dt page.dt order.dt search.dt', function() {
    convertTime();
  });
});
