def archive_posted_rows():
    try:
        fresh_data = worksheet.get_all_records()
        fresh_df   = pd.DataFrame(fresh_data)

        posted_indices = [
            i for i, row in fresh_df.iterrows()
            if str(row.get("Status", "")).strip() == "Posted"
            and str(row.get("R2Status", "")).strip() == "Deleted"
        ]

        if not posted_indices:
            print("ARCHIVE: No posted rows to archive")
            return

        try:
            archive_ws = sheet.worksheet("Archive")
        except Exception:
            archive_ws = sheet.add_worksheet(title="Archive", rows=1000, cols=20)
            headers = worksheet.row_values(1)
            archive_ws.append_row(headers)

        sheet_row_indices = sorted([i + 2 for i in posted_indices], reverse=True)

        rows_archived = 0
        for row_idx in sheet_row_indices:
            row_data = worksheet.row_values(row_idx)
            archive_ws.append_row(row_data)
            worksheet.delete_rows(row_idx)
            rows_archived += 1

        print(f"ARCHIVE: Moved {rows_archived} posted rows to Archive sheet")
        send_telegram(f"🗂️ Archived {rows_archived} posted rows to Archive sheet")

    except Exception as e:
        print("ARCHIVE ERROR:", str(e))
