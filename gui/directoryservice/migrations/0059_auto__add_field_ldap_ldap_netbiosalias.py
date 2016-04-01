# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


def netbios_split(netbiosname):
    parts = None
    if ',' in netbiosname:
        parts = netbiosname.split(',')
    elif ' ' in netbiosname:
        parts = netbiosname.split(' ')

    if not parts:
        return netbiosname, None
    else:
        netbiosname = parts[0]

        netbios_aliases = []
        if len(parts) > 1:
            for p in parts[1:]:
                if not p:
                    continue
                netbios_aliases.append(p)

        return netbiosname, ' '.join(netbios_aliases) or None


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'LDAP.ldap_netbiosalias'
        db.add_column(u'directoryservice_ldap', 'ldap_netbiosalias',
                      self.gf('django.db.models.fields.CharField')(max_length=120, null=True, blank=True),
                      keep_default=False)

        if not db.dry_run:
            ldap = orm['directoryservice.LDAP'].objects.latest('id')
            if not ldap:
                return
            ldap.ldap_netbiosname_a, ldap.ldap_netbiosalias = netbios_split(ldap.ldap_netbiosname_a)
            ldap.save()


    def backwards(self, orm):
        # Deleting field 'LDAP.ldap_netbiosalias'
        db.delete_column(u'directoryservice_ldap', 'ldap_netbiosalias')


    models = {
        u'directoryservice.activedirectory': {
            'Meta': {'object_name': 'ActiveDirectory'},
            'ad_allow_dns_updates': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'ad_allow_trusted_doms': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_bindname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_bindpw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_certificate': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['system.CertificateAuthority']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'ad_dcname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ad_disable_freenas_cache': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_dns_timeout': ('django.db.models.fields.IntegerField', [], {'default': '60'}),
            'ad_domainname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'ad_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_gcname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ad_idmap_backend': ('django.db.models.fields.CharField', [], {'default': "'rid'", 'max_length': '120'}),
            'ad_kerberos_principal': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['directoryservice.KerberosPrincipal']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'ad_kerberos_realm': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['directoryservice.KerberosRealm']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'ad_ldap_sasl_wrapping': ('django.db.models.fields.CharField', [], {'default': "'plain'", 'max_length': '120'}),
            'ad_netbiosalias': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ad_netbiosname_a': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ad_netbiosname_b': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ad_nss_info': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ad_site': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ad_ssl': ('django.db.models.fields.CharField', [], {'default': "'off'", 'max_length': '120'}),
            'ad_timeout': ('django.db.models.fields.IntegerField', [], {'default': '60'}),
            'ad_unix_extensions': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_use_default_domain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ad_verbose_logging': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        u'directoryservice.idmap_ad': {
            'Meta': {'object_name': 'idmap_ad'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_ad_range_high': ('django.db.models.fields.IntegerField', [], {'default': '90000000'}),
            'idmap_ad_range_low': ('django.db.models.fields.IntegerField', [], {'default': '10000'}),
            'idmap_ad_schema_mode': ('django.db.models.fields.CharField', [], {'default': "'rfc2307'", 'max_length': '120'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'})
        },
        u'directoryservice.idmap_adex': {
            'Meta': {'object_name': 'idmap_adex'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_adex_range_high': ('django.db.models.fields.IntegerField', [], {'default': '90000000'}),
            'idmap_adex_range_low': ('django.db.models.fields.IntegerField', [], {'default': '10000'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'})
        },
        u'directoryservice.idmap_autorid': {
            'Meta': {'object_name': 'idmap_autorid'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_autorid_ignore_builtin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'idmap_autorid_range_high': ('django.db.models.fields.IntegerField', [], {'default': '90000000'}),
            'idmap_autorid_range_low': ('django.db.models.fields.IntegerField', [], {'default': '10000'}),
            'idmap_autorid_rangesize': ('django.db.models.fields.IntegerField', [], {'default': '100000'}),
            'idmap_autorid_readonly': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'})
        },
        u'directoryservice.idmap_hash': {
            'Meta': {'object_name': 'idmap_hash'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'idmap_hash_range_high': ('django.db.models.fields.IntegerField', [], {'default': '100000000'}),
            'idmap_hash_range_low': ('django.db.models.fields.IntegerField', [], {'default': '90000001'}),
            'idmap_hash_range_name_map': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255'})
        },
        u'directoryservice.idmap_ldap': {
            'Meta': {'object_name': 'idmap_ldap'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'idmap_ldap_certificate': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['system.CertificateAuthority']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'idmap_ldap_ldap_base_dn': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'idmap_ldap_ldap_url': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'idmap_ldap_ldap_user_dn': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'idmap_ldap_range_high': ('django.db.models.fields.IntegerField', [], {'default': '90000000'}),
            'idmap_ldap_range_low': ('django.db.models.fields.IntegerField', [], {'default': '10000'}),
            'idmap_ldap_ssl': ('django.db.models.fields.CharField', [], {'default': "'off'", 'max_length': '120'})
        },
        u'directoryservice.idmap_nss': {
            'Meta': {'object_name': 'idmap_nss'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'idmap_nss_range_high': ('django.db.models.fields.IntegerField', [], {'default': '90000000'}),
            'idmap_nss_range_low': ('django.db.models.fields.IntegerField', [], {'default': '10000'})
        },
        u'directoryservice.idmap_rfc2307': {
            'Meta': {'object_name': 'idmap_rfc2307'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'idmap_rfc2307_bind_path_group': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'idmap_rfc2307_bind_path_user': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'idmap_rfc2307_certificate': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['system.CertificateAuthority']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'idmap_rfc2307_cn_realm': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'idmap_rfc2307_ldap_domain': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'idmap_rfc2307_ldap_realm': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'idmap_rfc2307_ldap_server': ('django.db.models.fields.CharField', [], {'default': "'ad'", 'max_length': '120'}),
            'idmap_rfc2307_ldap_url': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'idmap_rfc2307_ldap_user_dn': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'idmap_rfc2307_ldap_user_dn_password': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'idmap_rfc2307_range_high': ('django.db.models.fields.IntegerField', [], {'default': '90000000'}),
            'idmap_rfc2307_range_low': ('django.db.models.fields.IntegerField', [], {'default': '10000'}),
            'idmap_rfc2307_ssl': ('django.db.models.fields.CharField', [], {'default': "'off'", 'max_length': '120'}),
            'idmap_rfc2307_user_cn': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'directoryservice.idmap_rid': {
            'Meta': {'object_name': 'idmap_rid'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'idmap_rid_range_high': ('django.db.models.fields.IntegerField', [], {'default': '90000000'}),
            'idmap_rid_range_low': ('django.db.models.fields.IntegerField', [], {'default': '20000'})
        },
        u'directoryservice.idmap_tdb': {
            'Meta': {'object_name': 'idmap_tdb'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'idmap_tdb_range_high': ('django.db.models.fields.IntegerField', [], {'default': '100000000'}),
            'idmap_tdb_range_low': ('django.db.models.fields.IntegerField', [], {'default': '90000001'})
        },
        u'directoryservice.idmap_tdb2': {
            'Meta': {'object_name': 'idmap_tdb2'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'idmap_ds_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'idmap_ds_type': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'idmap_tdb2_range_high': ('django.db.models.fields.IntegerField', [], {'default': '100000000'}),
            'idmap_tdb2_range_low': ('django.db.models.fields.IntegerField', [], {'default': '90000001'}),
            'idmap_tdb2_script': ('freenasUI.freeadmin.models.fields.PathField', [], {'max_length': '255'})
        },
        u'directoryservice.kerberoskeytab': {
            'Meta': {'object_name': 'KerberosKeytab'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'keytab_file': ('django.db.models.fields.TextField', [], {}),
            'keytab_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'})
        },
        u'directoryservice.kerberosprincipal': {
            'Meta': {'object_name': 'KerberosPrincipal'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'principal_encryption': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'principal_keytab': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['directoryservice.KerberosKeytab']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'principal_name': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'principal_timestamp': ('django.db.models.fields.DateTimeField', [], {}),
            'principal_version': ('django.db.models.fields.IntegerField', [], {'default': '-1'})
        },
        u'directoryservice.kerberosrealm': {
            'Meta': {'object_name': 'KerberosRealm'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'krb_admin_server': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'krb_kdc': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'krb_kpasswd_server': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'krb_realm': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'})
        },
        u'directoryservice.kerberossettings': {
            'Meta': {'object_name': 'KerberosSettings'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ks_appdefaults_aux': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ks_libdefaults_aux': ('django.db.models.fields.TextField', [], {'blank': 'True'})
        },
        u'directoryservice.ldap': {
            'Meta': {'object_name': 'LDAP'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ldap_anonbind': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ldap_auxiliary_parameters': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'ldap_basedn': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_binddn': ('django.db.models.fields.CharField', [], {'max_length': '256', 'blank': 'True'}),
            'ldap_bindpw': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_certificate': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['system.CertificateAuthority']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'ldap_dns_timeout': ('django.db.models.fields.IntegerField', [], {'default': '10'}),
            'ldap_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ldap_groupsuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_has_samba_schema': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'ldap_hostname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_idmap_backend': ('django.db.models.fields.CharField', [], {'default': "'ldap'", 'max_length': '120'}),
            'ldap_kerberos_principal': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['directoryservice.KerberosPrincipal']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'ldap_kerberos_realm': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['directoryservice.KerberosRealm']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'}),
            'ldap_machinesuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_netbiosalias': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ldap_netbiosname_a': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_netbiosname_b': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'ldap_passwordsuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_schema': ('django.db.models.fields.CharField', [], {'default': "'rfc2307'", 'max_length': '120'}),
            'ldap_ssl': ('django.db.models.fields.CharField', [], {'default': "'off'", 'max_length': '120'}),
            'ldap_sudosuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'ldap_timeout': ('django.db.models.fields.IntegerField', [], {'default': '10'}),
            'ldap_usersuffix': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'})
        },
        u'directoryservice.nis': {
            'Meta': {'object_name': 'NIS'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nis_domain': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'nis_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nis_manycast': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nis_secure_mode': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nis_servers': ('django.db.models.fields.CharField', [], {'max_length': '8192', 'blank': 'True'})
        },
        u'directoryservice.nt4': {
            'Meta': {'object_name': 'NT4'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nt4_adminname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'nt4_adminpw': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'nt4_dcname': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'nt4_enable': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nt4_idmap_backend': ('django.db.models.fields.CharField', [], {'default': "'rid'", 'max_length': '120'}),
            'nt4_netbiosname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'blank': 'True'}),
            'nt4_use_default_domain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'nt4_workgroup': ('django.db.models.fields.CharField', [], {'max_length': '120'})
        },
        u'system.certificateauthority': {
            'Meta': {'object_name': 'CertificateAuthority'},
            'cert_CSR': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_certificate': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_chain': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'cert_city': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_common': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_country': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_digest_algorithm': ('django.db.models.fields.CharField', [], {'default': "'SHA256'", 'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_email': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_key_length': ('django.db.models.fields.IntegerField', [], {'default': '2048', 'null': 'True', 'blank': 'True'}),
            'cert_lifetime': ('django.db.models.fields.IntegerField', [], {'default': '3650', 'null': 'True', 'blank': 'True'}),
            'cert_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '120'}),
            'cert_organization': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_privatekey': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'cert_serial': ('django.db.models.fields.IntegerField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_signedby': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['system.CertificateAuthority']", 'null': 'True', 'blank': 'True'}),
            'cert_state': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True', 'blank': 'True'}),
            'cert_type': ('django.db.models.fields.IntegerField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        }
    }

    complete_apps = ['directoryservice']
