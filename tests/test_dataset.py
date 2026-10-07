from datetime import datetime, timezone
import hashlib
import pytest


def row(text, document='a', label='no_risk', method='project_curated', source='public_real'):
    return dict(text=text,label=label,agreement_family='loan',source_type=source,annotation_method=method,source_document_id=document,source_organization='TEST FIXTURE ONLY',source_url='https://www.consumerfinance.gov/' if source=='public_real' else None,retrieved_at=datetime.now(timezone.utc).isoformat(),sha256=hashlib.sha256(document.encode()).hexdigest(),is_hard_negative=False)


def test_metadata_and_taxonomy_validation():
    from training_pipeline.preprocessing.prepare import validate_rows
    assert len(validate_rows([row('The fixed repayment schedule is attached.')]))==1
    for bad in [dict(row('Term'),label='imaginary_risk'),dict(row('Term'),source_document_id=''),dict(row('Term'),sha256='invented'),dict(row('Term'),annotation_method='expert_bot'),dict(row('Term'),source_url='http://localhost')]:
        with pytest.raises(ValueError):
            validate_rows([bad])


def test_unicode_and_exact_duplicate_removal():
    from training_pipeline.preprocessing.prepare import prepare_splits
    rows=[row('The lender imposes a processing fee.', 'a'),row('The lender imposes a processing fee.  ','b'),row('Insurance benefits commence after a waiting period.','c','waiting_period'),row('The landlord shall give advance notice before visiting.','d')]
    result=prepare_splits(rows)
    assert result['report']['duplicates_removed']==1
    all_rows=sum([result[k] for k in ['train','validation','test']],[])
    assert len(all_rows)==3


def test_source_groups_and_near_duplicates_do_not_leak():
    from training_pipeline.preprocessing.prepare import prepare_splits
    rows=[row('A processing fee of one hundred rupees is payable before disbursement.','a','hidden_charges'),row('A processing fee of one hundred rupees is payable before loan disbursement.','b','hidden_charges'),row('The insurer excludes flood damage from all claims.','c','coverage_exclusion'),row('A tenant may inspect the rental property with prior agreement.','d'),row('The lender may seize collateral after the borrower defaults.','e','foreclosure'),row('The cardholder owes the balance on the stated payment date.','f')]
    result=prepare_splits(rows)
    seen={}
    for split in ['train','validation','test']:
        for item in result[split]:
            doc=item['source_document_id']
            assert doc not in seen or seen[doc]==split
            seen[doc]=split
    assert seen['a']==seen['b']
    assert result==prepare_splits(rows)


def test_weak_labels_are_excluded_from_ground_truth():
    from training_pipeline.preprocessing.prepare import prepare_splits
    rows=[row('The borrower pays the principal in full.','a'),row('The insurer excludes earthquake damage.','b','coverage_exclusion'),row('A lease runs for one calendar year.','c'),row('Weak fee match.', 'd','hidden_charges','weak_label')]
    result=prepare_splits(rows)
    assert result['report']['weak_label_count']==1
    assert all(item['annotation_method']!='weak_label' for key in ['train','validation','test'] for item in result[key])


def test_cross_split_validation_rejects_leaks():
    from training_pipeline.preprocessing.prepare import assert_no_leakage
    with pytest.raises(ValueError):
        assert_no_leakage({'train':[row('The processing fee must be paid in advance.','a')],'validation':[row('Other text.','a')],'test':[]})
    with pytest.raises(ValueError):
        assert_no_leakage({'train':[row('The processing fee must be paid in advance.','a')],'validation':[],'test':[row('The processing fee must be paid in advance!','b')]})


def test_training_guard_rejects_small_or_synthetic_evaluation():
    from training_pipeline.scripts.train import validate_training_data
    splits={key:[row('A clearly synthetic legal example.',key,source='synthetic',method='synthetic_curated')] for key in ['train','validation','test']}
    with pytest.raises(ValueError):
        validate_training_data(splits)


def test_evaluation_generates_requested_files(tmp_path):
    from training_pipeline.evaluation.metrics import write_evaluation
    rows=[row('A processing fee is charged.','a','hidden_charges'),row('There is no penalty.','b')]
    predictions=[{'hidden_charges':.9,'no_risk':.1},{'hidden_charges':.8,'no_risk':.2}]
    report=write_evaluation(rows,predictions,tmp_path)
    assert report['accuracy']==pytest.approx(.5)
    for name in ['metrics.json','classification_report.json','confusion_matrix.json','confusion_matrix.png','errors.jsonl']:
        assert (tmp_path/name).stat().st_size>0
    assert len((tmp_path/'errors.jsonl').read_text().splitlines())==1


def test_ingestion_rejects_untrusted_source_and_bad_checksums(tmp_path):
    from training_pipeline.ingestion.public_sources import validate_source, verify_checksum
    with pytest.raises(ValueError):
        validate_source({'url':'https://127.0.0.1/private','source_organization':'Local','agreement_family':'loan'})
    with pytest.raises(ValueError):
        verify_checksum(b'test','0'*64)
    assert verify_checksum(b'test',hashlib.sha256(b'test').hexdigest())


def test_chained_near_duplicates_share_group():
    from training_pipeline.preprocessing.prepare import prepare_splits
    texts=['The lender may charge a processing fee before the loan disbursement.', 'The lender may charge a processing fee before loan disbursement.', 'The lender may charge the processing fee before loan disbursement.']
    rows=[row(text,chr(97+i),'hidden_charges') for i,text in enumerate(texts)]+[row('The insurer covers hospitalization under the stated schedule.','x'),row('The tenant can end the lease after one month of written notice.','y')]
    result=prepare_splits(rows)
    owners={r['source_document_id']:key for key in ['train','validation','test'] for r in result[key]}
    assert owners['a']==owners['b']==owners['c']
